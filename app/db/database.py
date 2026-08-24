"""
Database setup and session management using SQLAlchemy.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},  # Required for SQLite
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that provides a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all database tables."""
    from app.core.models import (  # noqa: F401 — import to register models
        Payment,
        Settlement,
        BankEntry,
        Refund,
        ReconciliationResult,
        AuditLog,
    )

    Base.metadata.create_all(bind=engine)
