"""Fixtures for PostgreSQL-backed integration tests."""

import os
from collections.abc import Generator

import pytest

# A synthetic key keeps auth routes testable without adding a production secret.
os.environ["GRADTRACK_AUTH_SECRET_KEY"] = (
    "synthetic-only-gradtrack-auth-test-key-32-bytes-minimum"
)

from alembic import command
from alembic.config import Config
from app.config import Settings
from app.database import engine
from sqlalchemy import Engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session


@pytest.fixture(scope="session")
def postgres_engine() -> Generator[Engine, None, None]:
    """Connect only to a dedicated PostgreSQL test database and migrate it."""
    database_url = make_url(Settings.from_environment().database_url)
    if (
        database_url.drivername != "postgresql+psycopg"
        or not database_url.database
        or not database_url.database.lower().endswith("_test")
    ):
        pytest.fail(
            "PostgreSQL integration tests require GRADTRACK_DATABASE_URL to use "
            "postgresql+psycopg and a dedicated database name ending in '_test'."
        )

    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")

        command.upgrade(Config("alembic.ini"), "head")
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session(postgres_engine: Engine) -> Generator[Session, None, None]:
    """Roll back each integration test, including test-level commits."""
    with postgres_engine.connect() as connection:
        transaction = connection.begin()
        session = Session(bind=connection, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            session.close()
            transaction.rollback()
