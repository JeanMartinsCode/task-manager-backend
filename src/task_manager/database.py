"""Database configuration and session management."""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

# SQLite database URL
# Using SQLite with SQLAlchemy 2.0+ requires explicit sqlite:/// prefix
# StaticPool: recommended for SQLite with threading
DATABASE_URL = "sqlite:///./task_manager.db"

# Create database engine
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
