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
                "tasks",
                "task_checklist_items",
                "task_activities",
                "task_comments",
                "task_attachments",
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


def test_phase5b_data_survives_task_migration_and_downgrade(
    postgres_engine: Engine,
) -> None:
    schema = f"task_migration_{uuid4().hex}"
    with postgres_engine.begin() as connection:
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')

    try:
        with postgres_engine.connect() as connection:
            transaction = connection.begin()
            connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}", public')
            config = Config("alembic.ini")
            config.attributes["connection"] = connection

            # 1. Apply up to Phase 5B
            command.upgrade(config, "gt22_25_0004")
            student_id = uuid4()
            supervisor_id = uuid4()
            team_id = uuid4()
            milestone_id = uuid4()
            sub_id = uuid4()
            ver_id = uuid4()
            rev_id = uuid4()

            connection.execute(
                text(
                    "INSERT INTO users (id, email, password_hash, display_name, "
                    "system_role) VALUES "
                    "(:s_id, 'student@example.test', 'hash', 'Student', 'student'), "
                    "(:sup_id, 'supervisor@example.test', 'hash', 'Supervisor', "
                    "'supervisor')"
                ),
                {"s_id": student_id, "sup_id": supervisor_id},
            )
            connection.execute(
                text("INSERT INTO teams (id, name) VALUES (:id, 'Alpha')"),
                {"id": team_id},
            )
            connection.execute(
                text(
                    "INSERT INTO team_memberships (id, team_id, user_id, role) "
                    "VALUES (:id, :t_id, :u_id, 'leader')"
                ),
                {"id": uuid4(), "t_id": team_id, "u_id": student_id},
            )
            connection.execute(
                text(
                    "INSERT INTO supervisor_assignments (team_id, supervisor_id) "
                    "VALUES (:t_id, :sup_id)"
                ),
                {"t_id": team_id, "sup_id": supervisor_id},
            )
            connection.execute(
                text(
                    "INSERT INTO milestones (id, team_id, name, due_at) "
                    "VALUES (:m_id, :t_id, 'SRS', '2026-12-01T15:00:00Z')"
                ),
                {"m_id": milestone_id, "t_id": team_id},
            )
            connection.execute(
                text(
                    "INSERT INTO milestone_submissions "
                    "(id, milestone_id, review_status) "
                    "VALUES (:sub_id, :m_id, 'approved')"
                ),
                {"sub_id": sub_id, "m_id": milestone_id},
            )
            connection.execute(
                text(
                    "INSERT INTO submission_versions "
                    "(id, submission_id, version_number, submitted_by, submitted_at, "
                    "deadline_at_submission, is_late, source_type, url) "
                    "VALUES (:v_id, :sub_id, 1, :s_id, '2026-11-30T15:00:00Z', "
                    "'2026-12-01T15:00:00Z', false, 'link', 'https://example.org/srs')"
                ),
                {"v_id": ver_id, "sub_id": sub_id, "s_id": student_id},
            )
            connection.execute(
                text(
                    "INSERT INTO supervisor_reviews (id, version_id, reviewer_id, "
                    "decision, feedback, reviewed_at) VALUES (:rev_id, :v_id, "
                    ":sup_id, 'approved', 'Looks good', '2026-12-01T16:00:00Z')"
                ),
                {"rev_id": rev_id, "v_id": ver_id, "sup_id": supervisor_id},
            )

            # 2. Upgrade to head (gt26_27_0005)
            command.upgrade(config, "head")
            new_tables = {"tasks", "task_checklist_items", "task_activities"}
            assert new_tables <= set(inspect(connection).get_table_names())

            # 3. Insert task and checklist item
            task_id = uuid4()
            connection.execute(
                text(
                    "INSERT INTO tasks (id, team_id, title, status, priority, "
                    "created_by, assignee_id, updated_by) VALUES "
                    "(:task_id, :team_id, 'Verify migration', 'todo', 'medium', "
                    ":creator, :assignee, :creator)"
                ),
                {
                    "task_id": task_id,
                    "team_id": team_id,
                    "creator": student_id,
                    "assignee": student_id,
                },
            )
            chk_id = uuid4()
            connection.execute(
                text(
                    "INSERT INTO task_checklist_items (id, task_id, item_text, "
                    "is_done, created_by) VALUES (:chk_id, :task_id, 'Step 1', "
                    "false, :creator)"
                ),
                {"chk_id": chk_id, "task_id": task_id, "creator": student_id},
            )

            assert (
                connection.scalar(
                    text("SELECT count(*) FROM tasks WHERE id = :id"),
                    {"id": task_id},
                )
                == 1
            )

            # 4. Downgrade back to gt22_25_0004
            command.downgrade(config, "gt22_25_0004")
            remaining_tables = set(inspect(connection).get_table_names())
            assert not remaining_tables.intersection(new_tables)
            assert (
                connection.scalar(
                    text("SELECT count(*) FROM supervisor_reviews WHERE id = :id"),
                    {"id": rev_id},
                )
                == 1
            )
            assert (
                connection.scalar(
                    text("SELECT count(*) FROM submission_versions WHERE id = :id"),
                    {"id": ver_id},
                )
                == 1
            )

            # 5. Upgrade back to head
            command.upgrade(config, "head")
            assert new_tables <= set(inspect(connection).get_table_names())
            transaction.rollback()
    finally:
        with postgres_engine.begin() as connection:
            connection.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')


def test_phase6a_data_survives_collaboration_migration_and_downgrade(
    postgres_engine: Engine,
) -> None:
    schema = f"task_collab_mig_{uuid4().hex}"
    student_id = uuid4()
    team_id = uuid4()
    task_id = uuid4()
    comment_id = uuid4()
    attachment_id = uuid4()

    with postgres_engine.begin() as connection:
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')

    try:
        with postgres_engine.connect() as connection:
            transaction = connection.begin()
            connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}", public')
            config = Config("alembic.ini")
            config.attributes["connection"] = connection

            # 1. Upgrade to Phase 6A (gt26_27_0005)
            command.upgrade(config, "gt26_27_0005")

            connection.execute(
                text(
                    "INSERT INTO users (id, email, password_hash, display_name, "
                    "system_role) VALUES "
                    "(:s_id, 'student@example.test', 'hash', 'Student', 'student')"
                ),
                {"s_id": student_id},
            )
            connection.execute(
                text("INSERT INTO teams (id, name) VALUES (:id, 'Team Alpha')"),
                {"id": team_id},
            )
            connection.execute(
                text(
                    "INSERT INTO team_memberships (id, team_id, user_id, role) "
                    "VALUES (:id, :t_id, :u_id, 'leader')"
                ),
                {"id": uuid4(), "t_id": team_id, "u_id": student_id},
            )
            connection.execute(
                text(
                    "INSERT INTO tasks (id, team_id, title, status, priority, "
                    "created_by, assignee_id, updated_by) VALUES "
                    "(:task_id, :team_id, 'Build features', 'todo', 'medium', "
                    ":creator, :assignee, :creator)"
                ),
                {
                    "task_id": task_id,
                    "team_id": team_id,
                    "creator": student_id,
                    "assignee": student_id,
                },
            )

            # 2. Upgrade to Phase 6B (head: gt28_0006)
            command.upgrade(config, "head")
            collab_tables = {"task_comments", "task_attachments"}
            assert collab_tables <= set(inspect(connection).get_table_names())

            # 3. Insert comment and attachment
            connection.execute(
                text(
                    "INSERT INTO task_comments (id, task_id, author_id, content) "
                    "VALUES (:c_id, :task_id, :author_id, 'Great progress!')"
                ),
                {"c_id": comment_id, "task_id": task_id, "author_id": student_id},
            )
            connection.execute(
                text(
                    "INSERT INTO task_attachments (id, task_id, uploader_id, "
                    "storage_key, original_filename, file_size_bytes, media_type) "
                    "VALUES (:a_id, :task_id, :uploader_id, :key, :filename, :size, "
                    ":media)"
                ),
                {
                    "a_id": attachment_id,
                    "task_id": task_id,
                    "uploader_id": student_id,
                    "key": "a" * 64,
                    "filename": "notes.pdf",
                    "size": 1024,
                    "media": "application/pdf",
                },
            )
            connection.execute(
                text(
                    "INSERT INTO task_activities (id, task_id, actor_id, event_type, "
                    "details) VALUES (:act_id, :task_id, :actor_id, 'comment_added', "
                    "'Added a comment')"
                ),
                {"act_id": uuid4(), "task_id": task_id, "actor_id": student_id},
            )

            assert (
                connection.scalar(
                    text("SELECT count(*) FROM task_comments WHERE id = :id"),
                    {"id": comment_id},
                )
                == 1
            )
            assert (
                connection.scalar(
                    text("SELECT count(*) FROM task_attachments WHERE id = :id"),
                    {"id": attachment_id},
                )
                == 1
            )

            # 4. Downgrade back to gt26_27_0005
            # Remove activity rows with new events before downgrading check constraint
            connection.execute(
                text(
                    "DELETE FROM task_activities WHERE event_type IN "
                    "('comment_added', 'attachment_uploaded')"
                )
            )
            command.downgrade(config, "gt26_27_0005")
            remaining_tables = set(inspect(connection).get_table_names())
            assert not remaining_tables.intersection(collab_tables)
            assert (
                connection.scalar(
                    text("SELECT count(*) FROM tasks WHERE id = :id"),
                    {"id": task_id},
                )
                == 1
            )

            # 5. Upgrade back to head
            command.upgrade(config, "head")
            assert collab_tables <= set(inspect(connection).get_table_names())
            transaction.rollback()
    finally:
        with postgres_engine.begin() as connection:
            connection.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
