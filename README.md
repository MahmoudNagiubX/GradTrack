# GradTrack
A full-stack graduation project management platform featuring a React web dashboard, Flutter mobile companion, collaborative task management, milestone tracking, supervisor reviews, analytics, and smart notifications.

## Backend setup — Phase 2

The FastAPI backend provides process and database health endpoints, a migration-managed PostgreSQL persistence foundation, and manual student registration with Argon2id password hashing and short-lived JWT bearer access tokens. Team-management and graduation-project workflows remain later phases.

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

Authentication requires an environment-provided signing key with at least 32 UTF-8 bytes. Generate a local-only key before using authentication endpoints. The key is not stored in the repository; without a configured key, registration, login, and verification of a supplied token fail closed with HTTP 503 while process health remains available. `/auth/me` still returns HTTP 401 when no bearer token is supplied.

```powershell
$env:GRADTRACK_AUTH_SECRET_KEY = (& .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))").Trim()
```

```shell
export GRADTRACK_AUTH_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
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

### Manual authentication API

OpenAPI documentation is available at <http://127.0.0.1:8000/docs>. Authentication accepts JSON request bodies:

| Endpoint | Purpose | Result |
|---|---|---|
| `POST /auth/register` | Register a student account with normalized email, validated display name, and password | Public account fields; the server always assigns the `student` role |
| `POST /auth/login` | Verify email and password | A 15-minute `Bearer` access token |
| `GET /auth/me` | Read the authenticated account | ID, email, display name, and system role |

Send the login token in `Authorization: Bearer <access_token>` when calling `/auth/me`. Password hashes and plaintext passwords are never included in response schemas. Unknown accounts and wrong passwords use the same generic login error. A disabled account cannot log in or use a previously issued token. The shared auth module also provides server-side system-role and team-membership/leader dependencies for protected routes; no public supervisor/coordinator provisioning or role-elevation endpoint exists. Privileged-role accounts are created only by synthetic database fixtures in tests.

Passwords must contain 16–128 Unicode characters. The API accepts passphrases of 64 or more characters, Unicode, and spaces, and preserves password input exactly without trimming or truncating it. No uppercase/lowercase/digit/symbol combination is required. No reliable offline compromised-password blocklist is present in this repository, so GT-53 does not add one or introduce another dependency.

### Configuration

Configuration is read from environment variables. Defaults are safe for local development: debug mode is off and logging is set to `INFO`.

| Variable | Default | Allowed values |
|---|---|---|
| `GRADTRACK_APP_NAME` | `GradTrack API` | Non-empty text |
| `GRADTRACK_DEBUG` | `false` | `true`/`false`, `1`/`0`, `yes`/`no`, `on`/`off` |
| `GRADTRACK_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `GRADTRACK_DATABASE_URL` | `postgresql+psycopg://gradtrack:gradtrack@127.0.0.1:5432/gradtrack_dev` | PostgreSQL URL using the Psycopg 3 driver |
| `GRADTRACK_AUTH_SECRET_KEY` | No default | Required for authentication; at least 32 UTF-8 bytes |

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

The auth unit tests run without PostgreSQL. The full suite, including registration, login, token, disabled-user, authorization, database-constraint, and migration integration tests, requires the dedicated `gradtrack_test` PostgreSQL database. CI uses a separate ephemeral PostgreSQL 16 service and a synthetic auth secret.

GitHub Actions runs the backend tests and lint/format checks on pushes and pull requests targeting `develop` or `main`, using an ephemeral PostgreSQL 16 service and retaining repository structure validation.
