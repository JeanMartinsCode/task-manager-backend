"""Database configuration and session management."""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

# Overridable via the DATABASE_URL environment variable (see .env.example),
# falling back to a local SQLite file for development. Read at import time,
# after the package __init__ has loaded .env.
# Using SQLite with SQLAlchemy 2.0+ requires explicit sqlite:/// prefix
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./task_manager.db")

# Create database engine.
# NOTE: check_same_thread and StaticPool are SQLite-specific (StaticPool
# shares one connection across the API and scheduler threads). Pointing
# DATABASE_URL at another backend would require revisiting both.
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for all ORM models
Base = declarative_base()


def get_db():
    """
    Dependency injection for FastAPI.
    Yields a database session and ensures cleanup.

    Example:
        @app.get("/tasks")
        def get_tasks(db: Session = Depends(get_db)):
            return db.query(Task).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
