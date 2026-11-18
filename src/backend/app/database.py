"""SQLAlchemy engine, sessions, and database connection checks."""

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings

settings = Settings.from_environment()

# SQLAlchemy opens its first connection only when the engine is used.
engine = create_engine(
    settings.database_url,
    connect_args={"connect_timeout": 5},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db_session() -> Generator[Session, None, None]:
    """Yield a request-scoped session and always close it afterward."""
    with SessionLocal() as session:
        yield session


def check_database_connection() -> None:
    """Raise a SQLAlchemy error when PostgreSQL cannot execute a simple query."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
