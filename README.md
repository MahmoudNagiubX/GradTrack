# GradTrack
A full-stack graduation project management platform featuring a React web dashboard, Flutter mobile companion, collaborative task management, milestone tracking, supervisor reviews, analytics, and smart notifications.

## Backend setup — Phases 0–5A

The FastAPI backend provides process and database health endpoints, a migration-managed PostgreSQL persistence foundation, manual student registration with Argon2id password hashing and short-lived JWT bearer access tokens, team creation and membership, supervisor assignment, team-scoped milestone and deadline APIs, and first-version file or HTTPS-link milestone submissions with immutable deadline snapshots.

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

### Team and supervisor APIs

Team data is restricted server-side. `GET /teams` lists only a student's member teams or a supervisor's currently assigned teams. A coordinator can list all pilot teams. `GET /teams/{team_id}` follows the same access rules; unauthorized team reads return `404` to avoid disclosing whether another team's ID exists.

| Request | Permission | Behavior |
|---|---|---|
| `POST /teams` | Authenticated student | Creates a team and its first leader membership in one database transaction. |
| `GET /teams` | Authenticated account | Lists only teams allowed by the caller's membership, assignment, or coordinator role. |
| `GET /teams/{team_id}` | Member, currently assigned supervisor, or coordinator | Reads one authorized team and its member display names/roles. |
| `POST /teams/{team_id}/members` | Student who is that team's leader | Adds an existing active student as a regular member; duplicate membership returns `409`. |
| `PUT /teams/{team_id}/supervisor` | Authenticated Programme Coordinator | Assigns or reassigns the team's current supervisor. The selected account must be an active supervisor. |

The current schema has no `Programme` entity or team-to-programme relationship. For the single-programme pilot, coordinator assignment and team visibility are temporarily global across teams. Add programme-specific coordinator scoping when the schema supports multiple programmes. Students, team leaders, and supervisors cannot assign or change supervisor assignments.

### Milestone and deadline APIs

Milestones belong to a team in the current single-programme MVP. Team members, the team's currently assigned supervisor, and a coordinator can read them. A coordinator or the currently assigned supervisor can create a milestone and change its deadline; students and team leaders cannot write milestones. A former supervisor loses access after reassignment. Coordinator visibility and writes are temporarily global because the current schema has no `Programme` entity; scope coordinator access when programme membership is introduced.

| Request | Permission | Behavior |
|---|---|---|
| `GET /teams/{team_id}/milestones` | Team member, current supervisor, or coordinator | Returns an array ordered by UTC deadline and then milestone ID. An empty team returns `[]`; clients should show a friendly empty state. |
| `GET /teams/{team_id}/milestones/{milestone_id}` | Same team-scoped readers | Reads one milestone only through its owning team. Cross-team and mismatched IDs return `404`. |
| `POST /teams/{team_id}/milestones` | Coordinator or currently assigned supervisor | Creates a team-owned milestone with a nonblank name, optional description, and offset-aware `due_at`. |
| `PATCH /teams/{team_id}/milestones/{milestone_id}` | Coordinator or currently assigned supervisor | Changes only the deadline; the new value is saved and returned. Past deadlines are permitted. |

Example request bodies:

```json
{
  "name": "SRS",
  "description": "Submit the software requirements specification.",
  "due_at": "2026-12-01T17:00:00+02:00"
}
```

```json
{
  "due_at": "2026-12-03T15:00:00Z"
}
```

`due_at` must include a timezone offset. The API stores and returns it in UTC. Each response includes a derived `deadline_status`: `scheduled` when more than seven days remain, `due_soon` when the deadline is in the next seven days or is exactly at the current instant, and `overdue` only after the deadline has passed. This planning state is not persisted and is separate from Phase 5A's submission lateness and review state.

### Milestone submission APIs — Phase 5A

Only an active student who currently belongs to the milestone's team can create its first submission. A milestone can have one initial submission in this phase; a second attempt returns `409` and cannot replace the accepted version. Team members, the currently assigned supervisor, and a coordinator can list/read versions within their authorized team scope. Coordinator access is temporarily global for the single-programme pilot because the schema has no `Programme` entity. A former supervisor loses access after reassignment.

| Request | Permission | Behavior |
|---|---|---|
| `POST /teams/{team_id}/milestones/{milestone_id}/submissions/link` | Active student on the team | Accepts JSON containing one validated HTTPS URL. The server stores the URL without fetching or previewing it. |
| `POST /teams/{team_id}/milestones/{milestone_id}/submissions/file` | Active student on the team | Accepts one `multipart/form-data` part named `file` and stores it under a server-generated opaque key. |
| `GET /teams/{team_id}/milestones/{milestone_id}/submissions` | Authorized team reader | Lists immutable versions oldest to newest. |
| `GET /teams/{team_id}/milestones/{milestone_id}/submissions/{version_id}` | Authorized team reader | Reads version metadata without exposing the private storage key. |
| `GET /teams/{team_id}/milestones/{milestone_id}/submissions/{version_id}/download` | Authorized team reader; file versions only | Streams the file as an attachment after fresh authentication and current team authorization. |

Link requests use JSON, for example:

```json
{
  "url": "https://example.org/submissions/srs"
}
```

File requests use multipart form data with exactly one `file` field. Supported extensions are `.pdf`, `.docx`, `.pptx`, `.png`, `.jpg`, `.jpeg`, `.zip`, and `.txt`. Files must be nonempty and no larger than **20 MiB**; multipart request bodies are bounded to 21 MiB including framing. The API validates the extension and content signature/structure, rejects mismatched MIME types, checks UTF-8 text and bounded ZIP/OOXML metadata, and does not execute, extract, render, or scan uploaded content. The browser-provided MIME type is advisory. HTTPS links are limited to 2,048 characters and reject local/internal hosts, IP literals that are not globally routable, credentials, fragments, and non-HTTPS schemes. Links are stored as untrusted external content; the server never resolves or fetches them.

File uploads require `GRADTRACK_PRIVATE_UPLOAD_DIR` to point to an absolute private directory **outside the repository and any served/static directory**. The application creates the directory when permitted; missing, relative, inaccessible, repository-contained, or symlinked roots fail closed for file operations. Link submissions, authentication, and `/health` do not require this setting. Files are available only through the authorized download endpoint and are sent as attachments with `nosniff` and `no-store` headers. The database stores an immutable version record and an opaque storage key, never the bytes or an absolute path.

Set a local directory outside the checkout before starting the API. These are example locations, not credentials or repository-relative paths:

```powershell
$env:GRADTRACK_PRIVATE_UPLOAD_DIR = Join-Path $env:LOCALAPPDATA "GradTrack\private-uploads"
```

```shell
export GRADTRACK_PRIVATE_UPLOAD_DIR="$HOME/.local/share/gradtrack/private-uploads"
```

On Windows, restrict the directory's ACL to the service account and authorized local administrators using Windows security tools; POSIX permission bits do not secure Windows folders. Avoid web roots, synchronized/public folders, and repository paths. Keep this directory persistent for the local single-server demo and include it in an appropriate private backup if needed.

Example requests (replace the bearer token with the token returned by login):

```shell
curl -X POST http://127.0.0.1:8000/teams/TEAM_UUID/milestones/MILESTONE_UUID/submissions/link \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.org/submissions/srs"}'
```

```shell
curl -X POST http://127.0.0.1:8000/teams/TEAM_UUID/milestones/MILESTONE_UUID/submissions/file \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -F "file=@Synthetic-SRS.pdf;type=application/pdf"
```

The server captures `submitted_at` after file validation and while the milestone row is locked. Each immutable version stores the deadline snapshot and computes `is_late` as `submitted_at > deadline_at_submission`; submission exactly at the deadline is on time. Editing the milestone deadline later does not change a saved version. This `is_late` field is separate from Phase 4's derived `deadline_status` and from the initial `pending_review` state. Phase 5A does not implement approval, return, revision, reviewer comments, deletion, or retention workflows.

Local private storage is approved for the single-server course-development/demo MVP. It is not a multi-instance storage design or a production internet deployment. This phase does not provide antivirus scanning/content disarm, encryption-at-rest service, a total disk quota, a global concurrent-upload limit, automated cleanup, or backups; configure deployment/server limits for concurrent requests and available disk capacity. A process crash after a file is moved but before its database transaction commits can leave an unreferenced private file; handled errors remove temporary/uncommitted files. Do not commit upload data. Repository-root `.gradtrack-private-uploads/` and `.gradtrack-upload-staging/` paths are ignored as accidental local artifacts, but the application rejects repository-contained storage paths.

### Configuration

Configuration is read from environment variables. Defaults are safe for local development: debug mode is off and logging is set to `INFO`.

| Variable | Default | Allowed values |
|---|---|---|
| `GRADTRACK_APP_NAME` | `GradTrack API` | Non-empty text |
| `GRADTRACK_DEBUG` | `false` | `true`/`false`, `1`/`0`, `yes`/`no`, `on`/`off` |
| `GRADTRACK_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `GRADTRACK_DATABASE_URL` | `postgresql+psycopg://gradtrack:gradtrack@127.0.0.1:5432/gradtrack_dev` | PostgreSQL URL using the Psycopg 3 driver |
| `GRADTRACK_AUTH_SECRET_KEY` | No default | Required for authentication; at least 32 UTF-8 bytes |
| `GRADTRACK_PRIVATE_UPLOAD_DIR` | No default | Required for private file uploads/downloads; absolute path outside the repository and public roots |

For example, in PowerShell set `$env:GRADTRACK_DEBUG = "true"` before starting Uvicorn to enable local debug mode. Do not commit `.env` files or real database credentials.

### Phases 1–5A schema

- `users` stores UUID keys, lowercase/trimmed unique email, password-hash storage, a nonempty display name, active state, and timezone-aware timestamps. Allowed system roles are `student`, `supervisor`, and `coordinator`.
- `teams` stores UUID keys and nonblank names. A team can be unassigned.
- `team_memberships` references a user and team, permits `member` or `leader` as a team-scoped role, and prevents duplicate membership for the same user/team pair.
- `supervisor_assignments` stores only the current assignment. Its team key allows at most one current supervisor; absence of a row means unassigned. Reassignment updates that row, and the domain function verifies that the referenced user has the supervisor system role. This phase does not keep assignment history.
- `milestones` stores a UUID, owning team, trimmed name, optional description, required timezone-aware deadline, and creation/update timestamps. A team/deadline index supports ordered reads. The deadline status is derived at response time and is not stored.
- `milestone_submissions` stores at most one initial submission thread per milestone, with `pending_review` as its initial state.
- `submission_versions` stores version number, authenticated submitter, trusted UTC submission time, deadline snapshot, computed late flag, and exactly one HTTPS link or private-file metadata source. PostgreSQL prevents updates and deletes to accepted versions. Phase 5A accepts version 1 only; review/return/revision APIs are not implemented.

Review, return, revision, and approval actions remain outside Phase 5A.

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

The auth and milestone-rule unit tests run without PostgreSQL. The full suite, including registration, login, token, disabled-user, team and milestone authorization, timezone persistence, database-constraint, and migration integration tests, requires the dedicated `gradtrack_test` PostgreSQL database. CI uses a separate ephemeral PostgreSQL 16 service and a synthetic auth secret.

GitHub Actions runs the backend tests and lint/format checks on pushes and pull requests targeting `develop` or `main`, using an ephemeral PostgreSQL 16 service and retaining repository structure validation.
