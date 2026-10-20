"""Database engine and session management (FR-003, SEC-016)."""

from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy database models."""

    pass


def create_db_engine(database_url: str) -> Engine:
    """Create a database engine configured for SQLite or PostgreSQL.

    Args:
        database_url: Connection string (sqlite:///... or postgresql://...).

    Returns:
        Engine: Configured SQLAlchemy engine.
    """
    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    return create_engine(
        database_url,
        connect_args=connect_args,
        echo=False,
    )


def get_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a thread-safe session factory for the engine."""
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db(session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    """Provide a transactional database session."""
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def init_db(engine: Engine) -> None:
    """Create all tables directly in the database (useful for local dev/testing)."""
    Base.metadata.create_all(bind=engine)
