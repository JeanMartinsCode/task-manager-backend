"""Tests for Alembic database migration configuration."""

import shutil
import subprocess
from pathlib import Path

import pytest
import sqlalchemy
from alembic.config import Config

from alembic import command


class TestAlembicDirectory:
    """Verify Alembic directory structure exists."""

    def test_alembic_directory_exists(self) -> None:
        """Verify alembic/ directory and essential files exist."""
        alembic_dir = Path("alembic")
        assert alembic_dir.exists(), "alembic directory does not exist"
        assert alembic_dir.is_dir(), "alembic is not a directory"

        # Check essential files
        assert (
            alembic_dir / "env.py"
        ).exists(), "alembic/env.py does not exist"
        assert (
            alembic_dir / "script.py.mako"
        ).exists(), "alembic/script.py.mako does not exist"

        # Check versions directory
        versions_dir = alembic_dir / "versions"
        assert versions_dir.exists(), "alembic/versions directory does not exist"
        assert versions_dir.is_dir(), "alembic/versions is not a directory"


class TestAlembicConfiguration:
    """Verify Alembic configuration files."""

    def test_alembic_ini_exists_and_configured(self) -> None:
        """Verify alembic.ini exists with proper configuration."""
        alembic_ini = Path("alembic.ini")
        assert alembic_ini.exists(), "alembic.ini does not exist"

        content = alembic_ini.read_text()

        # Check required configuration sections
        assert "sqlalchemy.url" in content, "sqlalchemy.url not configured in alembic.ini"
        assert (
            "script_location" in content
        ), "script_location not configured in alembic.ini"

    def test_alembic_ini_has_correct_database_url(self) -> None:
        """Verify alembic.ini points to SQLite database."""
        alembic_ini = Path("alembic.ini")
        content = alembic_ini.read_text()

        # Extract the sqlalchemy.url line
        for line in content.split("\n"):
            if line.strip().startswith("sqlalchemy.url"):
                assert (
                    "sqlite" in line.lower()
                ), f"sqlalchemy.url should use SQLite: {line}"
                break
        else:
            pytest.fail("sqlalchemy.url not found in alembic.ini")


class TestAlembicEnvConfiguration:
    """Verify Alembic env.py is properly configured."""

    def test_alembic_env_imports_base(self) -> None:
        """Verify alembic/env.py imports Base from database module."""
        env_py_path = Path("alembic") / "env.py"
        assert env_py_path.exists(), "alembic/env.py does not exist"

        content = env_py_path.read_text()

        assert (
            "from src.task_manager.database import Base" in content
        ), "env.py does not import Base from database module"
        assert (
            "target_metadata = Base.metadata" in content
        ), "env.py does not set target_metadata = Base.metadata"

    def test_alembic_env_can_import_without_error(self) -> None:
        """Verify alembic/env.py can be imported without errors."""
        # This is tricky because env.py is not a standard module
        # Instead, verify by running alembic command
        result = subprocess.run(
            ["python", "-m", "alembic", "current"],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )

        # alembic current should work without errors
        # (even if no migrations applied yet)
        assert (
            result.returncode == 0
        ), f"alembic current failed: {result.stderr}"


@pytest.fixture
def isolated_alembic_config(tmp_path: Path) -> Config:
    """Alembic config pointed at a throwaway script_location + database.

    Revision generation must never touch the real alembic/versions/
    directory or task_manager.db - autogenerate always writes a new
    migration file, so running it against the real project on every test
    run would create/delete files as a side effect of testing.
    """
    tmp_alembic_dir = tmp_path / "alembic"
    shutil.copytree(
        Path("alembic"),
        tmp_alembic_dir,
        ignore=shutil.ignore_patterns("versions", "__pycache__"),
    )
    (tmp_alembic_dir / "versions").mkdir()

    # No config_file_name (unlike Config("alembic.ini")): env.py only calls
    # fileConfig() when one is set, and that call reconfigures the process's
    # root logger - fine for the real subprocess-isolated CLI, but it would
    # leak into and break other tests' logging assertions if run in-process.
    cfg = Config()
    cfg.set_main_option("script_location", str(tmp_alembic_dir))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{tmp_path / 'test.db'}")
    return cfg


class TestAlembicMigrations:
    """Verify Alembic can generate and execute migrations."""

    def test_initial_migration_can_be_generated(
        self, isolated_alembic_config: Config
    ) -> None:
        """Verify alembic can generate initial migration."""
        command.revision(isolated_alembic_config, autogenerate=True, message="initial")

        script_location = isolated_alembic_config.get_main_option("script_location")
        assert script_location is not None
        versions_dir = Path(script_location) / "versions"
        migration_files = [f for f in versions_dir.glob("*.py") if f.name != "__init__.py"]

        assert (
            len(migration_files) >= 1
        ), f"No migration files found. Found: {migration_files}"

    def test_migration_can_be_executed(self) -> None:
        """Verify migrations can be applied to database."""
        # Clean database first by removing task_manager.db
        db_file = Path("task_manager.db")
        if db_file.exists():
            # Close all database connections before deleting
            from src.task_manager.database import engine
            engine.dispose()
            db_file.unlink()

        # Now upgrade to head
        result_upgrade = subprocess.run(
            ["python", "-m", "alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )

        assert result_upgrade.returncode == 0, f"Migration upgrade failed: {result_upgrade.stderr}"

        # Verify alembic_version table exists in database
        from src.task_manager.database import SessionLocal

        session = SessionLocal()
        try:
            result = session.execute(
                sqlalchemy.text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'"
                )
            )
            row = result.fetchone()
            assert row is not None, "alembic_version table not found in database"
        finally:
            session.close()

    def test_migration_creates_models_tables_and_indexes(self) -> None:
        """Verify the migration creates the expected model tables and indexes."""
        from src.task_manager.database import SessionLocal, engine

        # Ensure migrations are applied to head
        result_upgrade = subprocess.run(
            ["python", "-m", "alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )
        assert result_upgrade.returncode == 0, f"Migration upgrade failed: {result_upgrade.stderr}"

        session = SessionLocal()
        try:
            tables_result = session.execute(
                sqlalchemy.text(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name IN ('users', 'tasks', 'notifications')"
                )
            )
            tables = {row[0] for row in tables_result.fetchall()}

            assert {"users", "tasks", "notifications"}.issubset(tables), (
                "Expected users, tasks, and notifications tables to be created"
            )

            index_result = session.execute(
                sqlalchemy.text(
                    "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='users'"
                )
            )
            user_indexes = {row[0] for row in index_result.fetchall()}
            assert "ix_users_email" in user_indexes, "Expected unique index on users.email"

            task_index_result = session.execute(
                sqlalchemy.text(
                    "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='tasks'"
                )
            )
            task_indexes = {row[0] for row in task_index_result.fetchall()}
            assert "ix_tasks_assigned_to" in task_indexes, "Expected index on tasks.assigned_to"

            notification_index_result = session.execute(
                sqlalchemy.text(
                    "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='notifications'"
                )
            )
            notification_indexes = {row[0] for row in notification_index_result.fetchall()}
            assert "ix_notifications_task_id" in notification_indexes, (
                "Expected index on notifications.task_id"
            )
        finally:
            session.close()
            engine.dispose()
