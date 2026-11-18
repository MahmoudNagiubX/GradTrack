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
                "milestones",
                "milestone_submissions",
                "submission_versions",
                "supervisor_reviews",
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


def test_phase3_data_survives_milestone_migration_and_downgrade(
    postgres_engine: Engine,
) -> None:
    schema = f"milestone_migration_{uuid4().hex}"
    student_id = uuid4()
    supervisor_id = uuid4()
    team_id = uuid4()
    milestone_id = uuid4()
    membership_id = uuid4()

    with postgres_engine.begin() as connection:
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')

    try:
        with postgres_engine.connect() as connection:
            transaction = connection.begin()
            connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}", public')
            config = Config("alembic.ini")
            config.attributes["connection"] = connection

            command.upgrade(config, "gt52_0001")
            connection.execute(
                text(
                    """
                    INSERT INTO users (
                        id, email, password_hash, display_name, system_role
                    )
                    VALUES (
                        :student_id, 'phase4-student@example.test', 'synthetic-hash',
                        'Synthetic Student', 'student'
                    ),
                           (:supervisor_id, 'phase4-supervisor@example.test',
                            'synthetic-hash', 'Synthetic Supervisor', 'supervisor')
                    """
                ),
                {"student_id": student_id, "supervisor_id": supervisor_id},
            )
            connection.execute(
                text(
                    "INSERT INTO teams (id, name) VALUES (:team_id, 'Synthetic Team')"
                ),
                {"team_id": team_id},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO team_memberships (id, team_id, user_id, role)
                    VALUES (:membership_id, :team_id, :student_id, 'leader')
                    """
                ),
                {
                    "membership_id": membership_id,
                    "team_id": team_id,
                    "student_id": student_id,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO supervisor_assignments (team_id, supervisor_id)
                    VALUES (:team_id, :supervisor_id)
                    """
                ),
                {"team_id": team_id, "supervisor_id": supervisor_id},
            )

            command.upgrade(config, "gt18_19_0002")
            connection.execute(
                text(
                    """
                    INSERT INTO milestones (id, team_id, name, due_at)
                    VALUES (:milestone_id, :team_id, 'Phase 4 milestone',
                            '2026-12-01T15:00:00Z')
                    """
                ),
                {"milestone_id": milestone_id, "team_id": team_id},
            )
            command.upgrade(config, "head")
            due_at_column = next(
                column
                for column in inspect(connection).get_columns("milestones")
                if column["name"] == "due_at"
            )
            assert due_at_column["nullable"] is False
            assert due_at_column["type"].timezone is True
            assert (
                connection.scalar(
                    text("SELECT count(*) FROM users WHERE id = :user_id"),
                    {"user_id": student_id},
                )
                == 1
            )
            assert (
                connection.scalar(
                    text("SELECT system_role FROM users WHERE id = :user_id"),
                    {"user_id": student_id},
                )
                == "student"
            )
            assert (
                connection.scalar(
                    text("SELECT count(*) FROM teams WHERE id = :team_id"),
                    {"team_id": team_id},
                )
                == 1
            )
            assert (
                connection.scalar(
                    text("SELECT count(*) FROM milestones WHERE id = :milestone_id"),
                    {"milestone_id": milestone_id},
                )
                == 1
            )
            assert (
                connection.scalar(
                    text("SELECT role FROM team_memberships WHERE id = :id"),
                    {"id": membership_id},
                )
                == "leader"
            )
            assert (
                connection.scalar(
                    text("SELECT count(*) FROM team_memberships WHERE id = :id"),
                    {"id": membership_id},
                )
                == 1
            )
            assert (
                connection.scalar(
                    text(
                        "SELECT supervisor_id FROM supervisor_assignments "
                        "WHERE team_id = :id"
                    ),
                    {"id": team_id},
                )
                == supervisor_id
            )
            assert (
                connection.scalar(
                    text(
                        "SELECT count(*) FROM supervisor_assignments "
                        "WHERE team_id = :id"
                    ),
                    {"id": team_id},
                )
                == 1
            )

            index = next(
                item
                for item in inspect(connection).get_indexes("milestones")
                if item["name"] == "ix_milestones_team_due_at"
            )
            assert index["column_names"] == ["team_id", "due_at"]
            milestone_columns = {
                column["name"]
                for column in inspect(connection).get_columns("milestones")
            }
            assert "deadline_status" not in milestone_columns

            command.downgrade(config, "gt52_0001")
            assert "milestones" not in inspect(connection).get_table_names()
            assert "milestone_submissions" not in inspect(connection).get_table_names()
            assert "submission_versions" not in inspect(connection).get_table_names()
            assert (
                connection.scalar(
                    text("SELECT count(*) FROM users WHERE id = :user_id"),
                    {"user_id": student_id},
                )
                == 1
            )
            assert (
                connection.scalar(
                    text(
                        "SELECT count(*) FROM supervisor_assignments "
                        "WHERE team_id = :id"
                    ),
                    {"id": team_id},
                )
                == 1
            )

            command.upgrade(config, "head")
            assert "milestones" in inspect(connection).get_table_names()
            assert "milestone_submissions" in inspect(connection).get_table_names()
            assert "submission_versions" in inspect(connection).get_table_names()
            transaction.rollback()
    finally:
        with postgres_engine.begin() as connection:
            connection.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')


def test_supervisor_review_migration_preserves_phase5a_data_and_round_trips(
    postgres_engine: Engine,
) -> None:
    schema = f"review_migration_{uuid4().hex}"
    student_id = uuid4()
    supervisor_id = uuid4()
    team_id = uuid4()
    milestone_id = uuid4()
    submission_id = uuid4()
    version_id = uuid4()

    with postgres_engine.begin() as connection:
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')

    try:
        with postgres_engine.connect() as connection:
            transaction = connection.begin()
            connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}", public')
            config = Config("alembic.ini")
            config.attributes["connection"] = connection
            command.upgrade(config, "gt20_21_0003")
            connection.execute(
                text(
                    "INSERT INTO users (id, email, password_hash, display_name, "
                    "system_role) VALUES (:student_id, 'phase5-student@example.test', "
                    "'synthetic-hash', 'Synthetic Student', 'student'), "
                    "(:supervisor_id, 'phase5-supervisor@example.test', "
                    "'synthetic-hash', 'Synthetic Supervisor', 'supervisor')"
                ),
                {"student_id": student_id, "supervisor_id": supervisor_id},
            )
            connection.execute(
                text("INSERT INTO teams (id, name) VALUES (:id, 'Synthetic Team')"),
                {"id": team_id},
            )
            connection.execute(
                text(
                    "INSERT INTO milestones (id, team_id, name, due_at) "
                    "VALUES (:id, :team_id, 'Synthetic SRS', '2026-12-01T15:00:00Z')"
                ),
                {"id": milestone_id, "team_id": team_id},
            )
            connection.execute(
                text(
                    "INSERT INTO milestone_submissions (id, milestone_id) "
                    "VALUES (:id, :milestone_id)"
                ),
                {"id": submission_id, "milestone_id": milestone_id},
            )
            connection.execute(
                text(
                    "INSERT INTO submission_versions (id, submission_id, "
                    "version_number, submitted_by, submitted_at, "
                    "deadline_at_submission, is_late, source_type, url) VALUES "
                    "(:id, :submission_id, 1, :student_id, '2026-11-30T15:00:00Z', "
                    "'2026-12-01T15:00:00Z', false, 'link', 'https://example.org/srs')"
                ),
                {
                    "id": version_id,
                    "submission_id": submission_id,
                    "student_id": student_id,
                },
            )

            command.upgrade(config, "head")
            connection.execute(
                text(
                    "INSERT INTO supervisor_reviews (id, version_id, reviewer_id, "
                    "decision, feedback, reviewed_at) VALUES (:id, :version_id, "
                    ":reviewer_id, 'returned', 'Revise.', '2026-12-01T16:00:00Z')"
                ),
                {
                    "id": uuid4(),
                    "version_id": version_id,
                    "reviewer_id": supervisor_id,
                },
            )
            assert (
                connection.scalar(
                    text("SELECT count(*) FROM submission_versions WHERE id = :id"),
                    {"id": version_id},
                )
                == 1
            )
            assert (
                connection.scalar(
                    text(
                        "SELECT count(*) FROM supervisor_reviews WHERE version_id = :id"
                    ),
                    {"id": version_id},
                )
                == 1
            )

            command.downgrade(config, "gt20_21_0003")
            assert "supervisor_reviews" not in inspect(connection).get_table_names()
            assert (
                connection.scalar(
                    text("SELECT count(*) FROM submission_versions WHERE id = :id"),
                    {"id": version_id},
                )
                == 1
            )
            triggers = (
                connection.execute(
                    text(
                        "SELECT tgname FROM pg_trigger "
                        "WHERE tgrelid = 'submission_versions'::regclass "
                        "AND NOT tgisinternal"
                    )
                )
                .scalars()
                .all()
            )
            assert "trg_submission_versions_immutable" in triggers

            command.upgrade(config, "head")
            assert "supervisor_reviews" in inspect(connection).get_table_names()
            transaction.rollback()
    finally:
        with postgres_engine.begin() as connection:
            connection.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
