"""Security regression tests for the email-uniqueness race condition (pentest round 2, #4, MÉDIO).

Root cause: `UserService.create_user` used a check-then-insert pattern
(`SELECT ... WHERE email = ?` followed by `INSERT`), which is not
atomic. Under concurrent requests with the same email, more than one
request can pass the SELECT check before any of them commits, so more
than one proceeds to INSERT. The database's real `unique=True`
constraint on `User.email` correctly rejects every extra INSERT, but
the resulting `sqlalchemy.exc.IntegrityError` was not caught anywhere,
so it fell through to the generic exception handler (500) instead of
the same 400 "email already exists" the non-concurrent path already
returns.

Deterministic reproduction, not real thread concurrency: this repo's
SQLite setup shares one physical connection across every session
(`StaticPool`, `check_same_thread=False` in database.py). Investigation
for this fix confirmed that genuinely concurrent OS threads hammering
that shared connection corrupt low-level cursor/row-fetch state (e.g.
`IndexError: tuple index out of range` from inside SQLAlchemy's row
processor) in ~75% of trials — a *separate*, pre-existing hazard of
this connection setup, unrelated to the email race and out of scope
here, that makes a raw thread-based test unreliable regardless of
whether the actual fix is correct.

Instead, two sequential sessions simulate the exact race window
deterministically: session A commits a user first; session B's own
existence check is forced (one-shot monkeypatch, scoped to a single
instance) to report "not found", exactly as it would have if it had
genuinely run *before* session A's commit. Session B's INSERT is then
completely real and hits the real UNIQUE constraint, raising a genuine
`IntegrityError` — same exception, same code path, no reliance on
thread-scheduling luck or unsafe concurrent access to the shared
connection.
"""

import pytest

from task_manager.database import Base, SessionLocal, engine
from task_manager.models import User
from task_manager.services import UserService


@pytest.fixture(autouse=True)
def setup_and_teardown_db():
    """Create and drop tables for each test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


class _EmptyQuery:
    """Stand-in for a SQLAlchemy Query whose `.filter(...).first()` finds nothing."""

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return None


def test_create_user_converts_concurrent_integrity_error_to_value_error(monkeypatch):
    """A real UNIQUE-constraint violation from a stale check is converted to ValueError.

    Session A really commits a user with `email`. Session B's existence
    check is forced to see "no existing user" (simulating that check
    having run before session A's commit, the actual race window), so
    it proceeds straight to a real INSERT — which collides with the row
    session A already committed, raising a genuine
    `sqlalchemy.exc.IntegrityError` at commit time.
    """
    email = "race@example.com"

    session_a = SessionLocal()
    try:
        winner = UserService.create_user(session_a, "Winner", email)
        assert winner.id is not None
    finally:
        session_a.close()

    session_b = SessionLocal()
    try:
        monkeypatch.setattr(session_b, "query", lambda *a, **kw: _EmptyQuery())

        with pytest.raises(ValueError, match="email already exists"):
            UserService.create_user(session_b, "Loser", email)
    finally:
        session_b.close()


def test_only_one_row_survives_the_race():
    """After the race, exactly one row exists for the contested email."""
    email = "race-persisted@example.com"

    session_a = SessionLocal()
    try:
        UserService.create_user(session_a, "Winner", email)
    finally:
        session_a.close()

    session_b = SessionLocal()
    try:
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(session_b, "query", lambda *a, **kw: _EmptyQuery())
            with pytest.raises(ValueError):
                UserService.create_user(session_b, "Loser", email)
    finally:
        session_b.close()

    verify_session = SessionLocal()
    try:
        matches = verify_session.query(User).filter(User.email == email).all()
        assert len(matches) == 1
        assert matches[0].name == "Winner"
    finally:
        verify_session.close()
