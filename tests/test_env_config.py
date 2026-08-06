"""Tests for environment-based configuration and .env loading.

These all run the probe in a *subprocess*: DATABASE_URL, RATE_LIMIT_WRITE and
MAX_BODY_BYTES are resolved when their module is first imported, so once the
test session has imported task_manager there is no way to re-evaluate them
in-process. A fresh interpreter per case is what actually proves the
behaviour a real deployment gets.
"""

import os
import subprocess
import sys
from pathlib import Path


def run_probe(code: str, cwd: Path, env: dict[str, str]) -> str:
    """Run `code` in a fresh interpreter and return its stdout, stripped."""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"probe failed (exit {result.returncode})\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    return result.stdout.strip()


def clean_env(**overrides: str) -> dict[str, str]:
    """Current environment minus the config vars these tests care about."""
    env = os.environ.copy()
    for key in ("API_KEY", "DATABASE_URL", "RATE_LIMIT_WRITE", "MAX_BODY_BYTES"):
        env.pop(key, None)
    env.update(overrides)
    return env


class TestDatabaseUrlConfiguration:
    """DATABASE_URL must be environment-overridable, with a working default."""

    def test_falls_back_to_local_sqlite_when_env_var_absent(self, tmp_path: Path) -> None:
        """With no DATABASE_URL set (and no .env), the bundled default applies."""
        output = run_probe(
            "from task_manager.database import DATABASE_URL; print(DATABASE_URL)",
            cwd=tmp_path,
            env=clean_env(),
        )

        assert output == "sqlite:///./task_manager.db"

    def test_respects_database_url_from_environment(self, tmp_path: Path) -> None:
        """An exported DATABASE_URL wins over the hardcoded default."""
        custom_url = f"sqlite:///{(tmp_path / 'custom.db').as_posix()}"

        output = run_probe(
            "from task_manager.database import DATABASE_URL; print(DATABASE_URL)",
            cwd=tmp_path,
            env=clean_env(DATABASE_URL=custom_url),
        )

        assert output == custom_url

    def test_engine_is_bound_to_the_configured_url(self, tmp_path: Path) -> None:
        """The override reaches the actual engine, not just the constant."""
        custom_url = f"sqlite:///{(tmp_path / 'engine.db').as_posix()}"

        output = run_probe(
            "from task_manager.database import engine; print(engine.url)",
            cwd=tmp_path,
            env=clean_env(DATABASE_URL=custom_url),
        )

        assert output == custom_url


class TestDotenvLoading:
    """A .env file must be enough on its own -- no manual shell export."""

    def test_env_file_supplies_api_key_without_manual_export(self, tmp_path: Path) -> None:
        """Regression: API_KEY defined only in .env is picked up on import.

        Before load_dotenv() was wired into the package __init__, .env was
        never read by anything, so following the documented setup
        (`cp .env.example .env`) left every /api/* request failing closed
        with 500 "API_KEY is not set".
        """
        (tmp_path / ".env").write_text("API_KEY=key-from-dotenv-file\n", encoding="utf-8")

        output = run_probe(
            "import os, task_manager; print(os.getenv('API_KEY'))",
            cwd=tmp_path,
            env=clean_env(),
        )

        assert output == "key-from-dotenv-file"

    def test_api_key_from_env_file_actually_authenticates(self, tmp_path: Path) -> None:
        """End to end: the key .env provides satisfies the auth dependency."""
        (tmp_path / ".env").write_text("API_KEY=key-from-dotenv-file\n", encoding="utf-8")

        output = run_probe(
            "import task_manager\n"
            "from task_manager.security import require_api_key\n"
            "require_api_key('key-from-dotenv-file')\n"
            "print('accepted')",
            cwd=tmp_path,
            env=clean_env(),
        )

        assert output == "accepted"

    def test_env_file_supplies_import_time_settings_too(self, tmp_path: Path) -> None:
        """.env must land before modules that read config at import time."""
        (tmp_path / ".env").write_text(
            "RATE_LIMIT_WRITE=7/minute\nMAX_BODY_BYTES=4096\n", encoding="utf-8"
        )

        output = run_probe(
            "from task_manager.rate_limit import RATE_LIMIT_WRITE\n"
            "from task_manager.body_limit import MAX_BODY_BYTES\n"
            "print(RATE_LIMIT_WRITE, MAX_BODY_BYTES)",
            cwd=tmp_path,
            env=clean_env(),
        )

        assert output == "7/minute 4096"

    def test_real_environment_variable_beats_env_file(self, tmp_path: Path) -> None:
        """Injected config stays authoritative -- a stray .env can't override it.

        This is what keeps CI and production deployments (which set real
        environment variables) safe from a leftover local .env.
        """
        (tmp_path / ".env").write_text("API_KEY=key-from-dotenv-file\n", encoding="utf-8")

        output = run_probe(
            "import os, task_manager; print(os.getenv('API_KEY'))",
            cwd=tmp_path,
            env=clean_env(API_KEY="key-from-real-environment"),
        )

        assert output == "key-from-real-environment"
