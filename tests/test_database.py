"""Tests for SQLite database and SQLAlchemy configuration."""

from pathlib import Path

import sqlalchemy


class TestEnvConfiguration:
    """Verify environment configuration for database."""

    def test_env_example_has_database_url(self) -> None:
        """Verify .env.example documents DATABASE_URL."""
        env_example_path = Path(".env.example")
        assert env_example_path.exists(), ".env.example file missing"

        content = env_example_path.read_text()

        assert "DATABASE_URL" in content, "DATABASE_URL not documented in .env.example"
        assert "sqlite" in content.lower(), "SQLite not mentioned in .env.example"


class TestSQLAlchemySetup:
    """Verify SQLAlchemy is properly configured."""

    def test_sqlalchemy_base_class_exists(self) -> None:
        """Verify SQLAlchemy Base class exists and is configured."""
        from task_manager.database import Base

        assert Base is not None, "Base class is None"
        assert hasattr(Base, "metadata"), "Base class missing metadata attribute"

    def test_session_local_factory_works(self) -> None:
        """Verify SessionLocal factory can create database sessions."""
        from task_manager.database import SessionLocal

        # Create a session
        session = SessionLocal()
        assert session is not None, "SessionLocal() returned None"

        # Should not raise error when closing
        session.close()

    def test_database_engine_configuration(self) -> None:
        """Verify SQLAlchemy engine is properly configured."""
        from task_manager.database import engine

        assert engine is not None, "Engine is None"

        # Verify it's using SQLite
        engine_url = str(engine.url).lower()
        assert (
            "sqlite" in engine_url
        ), f"Engine not using SQLite. URL: {engine.url}"
        assert (
            "sqlite:///" in engine_url
        ), f"Invalid SQLite URL format. URL: {engine.url}"


class TestDatabaseConnection:
    """Verify actual database connection works."""

    def test_database_connection_works(self) -> None:
        """Verify database connection is functional."""
        from task_manager.database import Base, SessionLocal, engine

        # Create all tables (they should be empty for now)
        Base.metadata.create_all(bind=engine)

        # Create a session and verify we can query
        session = SessionLocal()

        try:
            # Execute a simple SQLite query
            result = session.execute(sqlalchemy.text("SELECT 1"))
            assert result is not None, "Query result is None"

            # Fetch the result
            row = result.fetchone()
            assert row is not None, "No result from query"
            assert row[0] == 1, f"Expected 1, got {row[0]}"

        finally:
            session.close()

    def test_database_file_created(self) -> None:
        """Verify database file is created after connection."""
        from task_manager.database import Base, engine

        # Create all tables (triggers DB file creation)
        Base.metadata.create_all(bind=engine)

        # Database file should exist
        db_file = Path("task_manager.db")
        assert db_file.exists(), "Database file not created at task_manager.db"
