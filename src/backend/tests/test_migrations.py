"""Alembic lifecycle tests in an isolated PostgreSQL schema."""

from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect, text

pytestmark = pytest.mark.postgresql


def test_empty_schema_can_upgrade_downgrade_and_upgrade_again(
    postgres_engine: Engine,
) -> None:
    schema = f"migration_test_{uuid4().hex}"
    with postgres_engine.begin() as connection:
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')

    try:
        with postgres_engine.connect() as connection:
            transaction = connection.begin()
            connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}", public')
            config = Config("alembic.ini")
            config.attributes["connection"] = connection

            command.upgrade(config, "head")
            expected_tables = {
                "alembic_version",
                "users",
                "teams",
                "team_memberships",
                "supervisor_assignments",
            }
            assert expected_tables <= set(inspect(connection).get_table_names())

            command.downgrade(config, "base")
            remaining = set(inspect(connection).get_table_names())
            assert not remaining.intersection(expected_tables - {"alembic_version"})
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                is None
            )

            command.upgrade(config, "head")
            assert expected_tables <= set(inspect(connection).get_table_names())
            transaction.rollback()
    finally:
        with postgres_engine.begin() as connection:
            connection.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
