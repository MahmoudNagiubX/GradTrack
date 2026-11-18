"""Alembic environment for the GradTrack SQLAlchemy models."""

from logging.config import fileConfig

from alembic import context
from app.config import Settings
from app.models import Base
from sqlalchemy import create_engine
from sqlalchemy.engine import Connection
from sqlalchemy.pool import NullPool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Generate SQL without opening a database connection."""
    context.configure(
        url=Settings.from_environment().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def _run_with_connection(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations on a new connection or a caller-provided one."""
    supplied_connection = config.attributes.get("connection")
    if supplied_connection is not None:
        _run_with_connection(supplied_connection)
        return

    connectable = create_engine(
        Settings.from_environment().database_url,
        connect_args={"connect_timeout": 5},
        poolclass=NullPool,
    )
    try:
        with connectable.connect() as connection:
            _run_with_connection(connection)
    finally:
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
