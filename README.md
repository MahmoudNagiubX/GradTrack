# GradTrack
A full-stack graduation project management platform featuring a React web dashboard, Flutter mobile companion, collaborative task management, milestone tracking, supervisor reviews, analytics, and smart notifications.

## Backend setup — Phase 1

The FastAPI backend provides process and database health endpoints plus a migration-managed PostgreSQL persistence foundation for users, teams, memberships, and current supervisor assignments. Registration, authentication, and graduation-project workflows are later phases.

Use Python 3.12 or newer. From the repository root, create the backend virtual environment and move into the backend directory:

```powershell
cd src/backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

On macOS or Linux, use the environment's `python` executable instead:

```shell
cd src/backend
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

### PostgreSQL configuration

Install and start PostgreSQL locally before running migrations or database integration tests. The application defaults to the local development URL below; it contains only placeholder development credentials. Set `GRADTRACK_DATABASE_URL` in the environment to use another PostgreSQL instance.

| Variable | Default | Purpose |
|---|---|---|
| `GRADTRACK_DATABASE_URL` | `postgresql+psycopg://gradtrack:gradtrack@127.0.0.1:5432/gradtrack_dev` | PostgreSQL connection for the app and Alembic |

For a local PostgreSQL installation, create the two development databases and role once (run from a shell with `psql` access to the local server):

```shell
psql -U postgres -c "CREATE ROLE gradtrack WITH LOGIN PASSWORD 'gradtrack';"
psql -U postgres -c "CREATE DATABASE gradtrack_dev OWNER gradtrack;"
psql -U postgres -c "CREATE DATABASE gradtrack_test OWNER gradtrack;"
```

In PowerShell, set the development URL and apply the schema migration from `src/backend`:

```powershell
$env:GRADTRACK_DATABASE_URL = "postgresql+psycopg://gradtrack:gradtrack@127.0.0.1:5432/gradtrack_dev"
.\.venv\Scripts\alembic.exe upgrade head
```

On macOS or Linux:

```shell
export GRADTRACK_DATABASE_URL="postgresql+psycopg://gradtrack:gradtrack@127.0.0.1:5432/gradtrack_dev"
.venv/bin/alembic upgrade head
```

### Run the API

From `src/backend`, start the API on the local machine.

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1
```

```shell
.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1
```

The process health endpoint is available at <http://127.0.0.1:8000/health> and returns `{"status":"ok"}` without requiring a database connection. <http://127.0.0.1:8000/health/database> checks PostgreSQL connectivity and returns HTTP 503 with a generic error when the database is unavailable. Stop the server with `Ctrl+C`.

### Configuration

Configuration is read from environment variables. Defaults are safe for local development: debug mode is off and logging is set to `INFO`.

| Variable | Default | Allowed values |
|---|---|---|
| `GRADTRACK_APP_NAME` | `GradTrack API` | Non-empty text |
| `GRADTRACK_DEBUG` | `false` | `true`/`false`, `1`/`0`, `yes`/`no`, `on`/`off` |
| `GRADTRACK_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `GRADTRACK_DATABASE_URL` | `postgresql+psycopg://gradtrack:gradtrack@127.0.0.1:5432/gradtrack_dev` | PostgreSQL URL using the Psycopg 3 driver |

For example, in PowerShell set `$env:GRADTRACK_DEBUG = "true"` before starting Uvicorn to enable local debug mode. Do not commit `.env` files or real database credentials.

### Phase 1 schema

- `users` stores UUID keys, lowercase/trimmed unique email, password-hash storage, a nonempty display name, active state, and timezone-aware timestamps. Allowed system roles are `student`, `supervisor`, and `coordinator`.
- `teams` stores UUID keys and nonblank names. A team can be unassigned.
- `team_memberships` references a user and team, permits `member` or `leader` as a team-scoped role, and prevents duplicate membership for the same user/team pair.
- `supervisor_assignments` stores only the current assignment. Its team key allows at most one current supervisor; absence of a row means unassigned. Reassignment updates that row, and the domain function verifies that the referenced user has the supervisor system role. This phase does not keep assignment history.

No milestone, submission, authentication endpoint, or other conceptual entity is created in this phase.

### Tests and code checks

Database tests use a dedicated database whose name ends with `_test`; they never fall back to SQLite. The test fixture applies Alembic migrations and rolls each integration test back. Migration lifecycle checks use a temporary PostgreSQL schema. Set the test URL before running tests.

Run these commands from `src/backend` in PowerShell:

```powershell
$env:GRADTRACK_DATABASE_URL = "postgresql+psycopg://gradtrack:gradtrack@localhost:5432/gradtrack_test"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\ruff.exe check app tests migrations
.\.venv\Scripts\ruff.exe format --check app tests migrations
```

On macOS or Linux, use:

```shell
export GRADTRACK_DATABASE_URL="postgresql+psycopg://gradtrack:gradtrack@localhost:5432/gradtrack_test"
.venv/bin/python -m pytest
.venv/bin/ruff check app tests migrations
.venv/bin/ruff format --check app tests migrations
```

GitHub Actions runs the backend tests and lint/format checks on pushes and pull requests targeting `develop` or `main`, using an ephemeral PostgreSQL 16 service and retaining repository structure validation.
