# GradTrack
A full-stack graduation project management platform featuring a React web dashboard, Flutter mobile companion, collaborative task management, milestone tracking, supervisor reviews, analytics, and smart notifications.

## Backend setup - Phases 0-5B

The FastAPI backend provides process and database health endpoints, a migration-managed PostgreSQL persistence foundation, manual student registration with Argon2id password hashing and short-lived JWT bearer access tokens, team creation and membership, supervisor assignment, team-scoped milestone and deadline APIs, and first-version file or HTTPS-link milestone submissions, supervisor reviews, feedback, approval, and returned-version revisions with immutable deadline snapshots.

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
| `GET /auth/me` | Read the authenticated account | ID, email, display name, system role, and optional academic/profile details (`student_number`, `faculty`, `department`, `academic_level`, `bio`, `has_avatar`) |
| `PATCH /auth/me` | Update permitted profile fields for the authenticated account | Updated profile representation; `display_name`, `student_number`, `faculty`, `department`, `academic_level`, `bio` can be edited; system role and auth properties are strictly forbidden |
| `POST /auth/me/avatar` | Upload or replace user profile photo | Validates PNG/JPEG format (up to 2 MiB), stages privately, and updates `has_avatar` |
| `DELETE /auth/me/avatar` | Remove user profile photo | Clears avatar reference and safely removes the stored file (idempotent) |
| `GET /auth/me/avatar` | Stream authenticated user's own profile photo | Image stream (`image/png` or `image/jpeg`) with nosniff and private cache headers |

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
| `GET /teams/{team_id}/members/{user_id}/profile` | Member, currently assigned supervisor, or coordinator | Reads limited display profile of a team member (name, team role, academic attributes, avatar flag; email and student number suppressed). |
| `GET /teams/{team_id}/members/{user_id}/avatar` | Member, currently assigned supervisor, or coordinator | Streams an authorized team member's avatar photo (`image/png` or `image/jpeg`). |

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

The server captures `submitted_at` after file validation and while the milestone row is locked. Each immutable version stores the deadline snapshot and computes `is_late` as `submitted_at > deadline_at_submission`; submission exactly at the deadline is on time. Editing the milestone deadline later does not change a saved version. This `is_late` field is separate from Phase 4's derived `deadline_status` and from the initial `pending_review` state. Phase 5A alone did not implement review or revision workflows; Phase 5B adds the scoped review flow described below. Deletion and retention automation remain out of scope.

Local private storage is approved for the single-server course-development/demo MVP. It is not a multi-instance storage design or a production internet deployment. This phase does not provide antivirus scanning/content disarm, encryption-at-rest service, a total disk quota, a global concurrent-upload limit, automated cleanup, or backups; configure deployment/server limits for concurrent requests and available disk capacity. A process crash after a file is moved but before its database transaction commits can leave an unreferenced private file; handled errors remove temporary/uncommitted files. Do not commit upload data. Repository-root `.gradtrack-private-uploads/` and `.gradtrack-upload-staging/` paths are ignored as accidental local artifacts, but the application rejects repository-contained storage paths.

### Supervisor review and revision APIs - Phase 5B

The review workflow uses the existing submission thread and private storage. The authenticated active supervisor currently assigned to a team may decide its latest pending version. A return requires 1-2000 characters of trimmed feedback; approval may include optional feedback. Students, team leaders, coordinators, other supervisors, and former supervisors cannot approve or return submissions. In this single-programme pilot, coordinators retain global read oversight but cannot write reviews.

| Request | Permission | Behavior |
|---|---|---|
| `GET /supervisor/submissions/pending` | Active supervisor | Lists only latest pending versions from currently assigned teams, ordered by submission time and version ID. |
| `POST /teams/{team_id}/milestones/{milestone_id}/submissions/{version_id}/review` | Current assigned supervisor | Records one immutable `approved` or `returned` review for the latest pending version. |
| `GET /teams/{team_id}/milestones/{milestone_id}/submissions/{version_id}/review` | Authorized team reader | Reads the immutable feedback for that version; absent reviews return `404`. |
| `POST /teams/{team_id}/milestones/{milestone_id}/submissions/revisions/link` | Active student team member | Appends a validated HTTPS link as a new version, only after the latest version is returned. |
| `POST /teams/{team_id}/milestones/{milestone_id}/submissions/revisions/file` | Active student team member | Appends a validated private file as a new version, only after the latest version is returned. |

A pending version cannot be replaced. A returned version can receive one new link or file version, which returns the thread to `pending_review`; each version retains its own review status and feedback. Approval is final. Every version keeps its own submission timestamp, deadline snapshot, and late flag. Review and revision operations lock the submission thread before changing its state, and PostgreSQL prevents edits or deletion of review and version history. Existing secure download authorization applies to revised files as well.

### Team Task Management APIs — Phase 6A

Phase 6A implements team-scoped task management, assignment, progress updates, one-level subtasks, checklists, and append-only audit activity.

| Request | Permission | Behavior |
|---|---|---|
| `GET /teams/{team_id}/tasks` | Current team viewer | Lists team tasks; supports filters (`status`, `assignee_id`, `priority`, `milestone_id`, `due_before`, `due_after`, `parent_task_id`). |
| `GET /teams/{team_id}/tasks/{task_id}` | Current team viewer | Detailed task view including child subtasks and ordered checklist items. |
| `POST /teams/{team_id}/tasks` | Active team leader | Creates and assigns task to an active student member of the same team; optional same-team milestone and 1-level parent task. |
| `PATCH /teams/{team_id}/tasks/{task_id}` | Active team leader | Updates task metadata, priority, due date, estimated minutes, milestone, parent, or reassigns task. |
| `PATCH /teams/{team_id}/tasks/{task_id}/status` | Assignee or team leader | Updates progress (`todo` ↔ `in_progress` ↔ `done`); marks completion timestamp/actor; reopening clears completion metadata. |
| `GET /teams/{team_id}/tasks/{task_id}/activity` | Current team viewer | Chronological immutable audit history of task mutations. |
| `POST /teams/{team_id}/tasks/{task_id}/checklist` | Active team leader | Adds a checklist item to a task. |
| `PATCH /teams/{team_id}/tasks/{task_id}/checklist/{item_id}` | Assignee or team leader | Marks checklist item done/incomplete; leader may also edit text. |

Example task creation payload:
```json
{
  "title": "Implement authentication API",
  "description": "Argon2id password hashing and JWT sessions",
  "assignee_id": "STUDENT_UUID",
  "priority": "high",
  "due_at": "2026-12-15T15:00:00Z",
  "estimated_minutes": 180,
  "milestone_id": "MILESTONE_UUID"
}
```

Example status change payload:
```json
{
  "status": "in_progress"
}
```

### Team Task Collaboration APIs — Phase 6B

Phase 6B introduces team-scoped task comments and validated private file/image attachments with authorized streaming downloads.

| Request | Permission | Behavior |
|---|---|---|
| `GET /teams/{team_id}/tasks/{task_id}/comments` | Current team viewer | Lists chronological comments on a task with author attribution and UTC timestamps. |
| `POST /teams/{team_id}/tasks/{task_id}/comments` | Active team student member | Posts an append-only comment (1–2000 chars trimmed); records `comment_added` activity. |
| `GET /teams/{team_id}/tasks/{task_id}/attachments` | Current team viewer | Lists metadata for private attachments (original filename, size, media type, uploader). |
| `POST /teams/{team_id}/tasks/{task_id}/attachments` | Active team student member | Uploads a validated private file or image (up to 20 MiB); records `attachment_uploaded` activity. |
| `GET /teams/{team_id}/tasks/{task_id}/attachments/{attachment_id}/download` | Current team viewer | Private streaming download with `nosniff`, `no-store`, and RFC 5987 `Content-Disposition`. |

Example comment payload:
```json
{
  "content": "Drafted the initial C4 container diagram."
}
```

### Timeline / Calendar Data and Progress Dashboards — Phase 7A

Phase 7A introduces unified timeline calendar data and derived progress summaries for student teams and assigned supervisors. All metrics are computed dynamically from existing tables without adding database tables or scheduled aggregation jobs.

| Request | Permission | Behavior |
|---|---|---|
| `GET /teams/{team_id}/calendar?start_at=...&end_at=...` | Current team viewer | Returns unified chronological tasks and milestones in the half-open range `[start_at, end_at)`. Tasks with `due_at = NULL` are omitted. Maximum range is 93 days. |
| `GET /teams/{team_id}/progress` | Current team viewer | Returns derived progress metrics for the team: task lifecycle/overdue counts, assignee task breakdowns, milestone review/deadline counts, late submission count, and upcoming deadlines within 14 days. |
| `GET /supervisor/teams/progress` | Active supervisor | Returns an array of derived progress summaries for all teams currently assigned to the authenticated supervisor, ordered alphabetically by team name. |

Calendar queries require UTC offset-aware ISO 8601 timestamps and validate `start_at < end_at` with a maximum window of 93 days:
```text
GET /teams/{team_id}/calendar?start_at=2026-12-01T00:00:00Z&end_at=2026-12-31T23:59:59Z
```

Example calendar item (discriminated union by `kind`):
```json
[
  {
    "id": "TASK_UUID",
    "team_id": "TEAM_UUID",
    "title": "Setup PostgreSQL database",
    "due_at": "2026-12-05T18:00:00Z",
    "kind": "task",
    "status": "in_progress",
    "priority": "high",
    "assignee_id": "STUDENT_UUID",
    "milestone_id": "MILESTONE_UUID"
  },
  {
    "id": "MILESTONE_UUID",
    "team_id": "TEAM_UUID",
    "title": "Sprint 1 Review",
    "due_at": "2026-12-10T12:00:00Z",
    "kind": "milestone",
    "deadline_status": "due_soon",
    "review_status": "pending_review"
  }
]
```

Example team progress summary:
```json
{
  "team_id": "TEAM_UUID",
  "team_name": "Alpha Team",
  "as_of": "2026-12-01T12:00:00Z",
  "tasks": {
    "total": 10,
    "todo": 3,
    "in_progress": 4,
    "done": 3,
    "overdue": 1
  },
  "tasks_by_assignee": [
    {
      "user_id": "STUDENT_UUID",
      "display_name": "Student A",
      "total": 5,
      "todo": 1,
      "in_progress": 2,
      "done": 2,
      "overdue": 1
    }
  ],
  "milestones": {
    "total": 4,
    "scheduled": 2,
    "due_soon": 1,
    "overdue": 1,
    "not_submitted": 2,
    "pending_review": 1,
    "returned": 0,
    "approved": 1
  },
  "late_submissions": 1,
  "upcoming": [
    {
      "kind": "task",
      "id": "TASK_UUID",
      "title": "Design ERD",
      "due_at": "2026-12-03T15:00:00Z",
      "status": "in_progress",
      "priority": "high",
      "assignee_id": "STUDENT_UUID"
    }
  ]
}
```

### In-App Deadline Reminders — Phase 7B

Phase 7B provides pull-based in-app deadline reminders and read receipts for active student team members. Reminder notifications are derived dynamically from existing tasks and milestones on-the-fly when the app opens or refreshes.

> **Operational Notice:** Reminders are retrieved upon active application connection (pull model). No passive background daemons, Celery/cron tasks, WebSockets, or push notifications run when the server or client is closed.

| Request | Permission | Behavior |
|---|---|---|
| `GET /notifications` | Active student team member | Returns chronological due-soon (`<= 7 days`) and overdue reminders for assigned tasks and actionable team milestones (`not_submitted` or `returned`), with read states. |
| `GET /notifications?unread_only=true` | Active student team member | Same as above, filtering out reminders marked as read. |
| `POST /notifications/{reminder_id}/read` | Active student team member | Marks a currently active reminder as read for the calling student. Idempotent. |

Reminder IDs are generated deterministically using UUIDv5 from `source_kind + source_id + UTC due_at + reminder_kind`. If a task or milestone deadline is changed, the outdated reminder disappears from the live list and a fresh unread reminder appears with a new ID once it falls within the 7-day window. Non-student roles receive `403 Forbidden`. Attempting to mark an unknown or stale reminder returns `404 Not Found`.

Example reminder payload:
```json
[
  {
    "id": "REMINDER_UUID",
    "kind": "task_due_soon",
    "source_id": "TASK_UUID",
    "team_id": "TEAM_UUID",
    "title": "Implement authentication endpoints",
    "due_at": "2026-12-15T15:00:00Z",
    "is_read": false,
    "read_at": null
  }
]
```

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

### Phases 1–7B schema

- `users` stores UUID keys, lowercase/trimmed unique email, password-hash storage, a nonempty display name, active state, and timezone-aware timestamps. Allowed system roles are `student`, `supervisor`, and `coordinator`.
- `teams` stores UUID keys and nonblank names. A team can be unassigned.
- `team_memberships` references a user and team, permits `member` or `leader` as a team-scoped role, and prevents duplicate membership for the same user/team pair.
- `supervisor_assignments` stores only the current assignment. Its team key allows at most one current supervisor; absence of a row means unassigned. Reassignment updates that row, and the domain function verifies that the referenced user has the supervisor system role. This phase does not keep assignment history.
- `milestones` stores a UUID, owning team, trimmed name, optional description, required timezone-aware deadline, and creation/update timestamps. A team/deadline index supports ordered reads. The deadline status is derived at response time and is not stored.
- `milestone_submissions` stores at most one initial submission thread per milestone, with `pending_review` as its initial state.
- `submission_versions` stores version number, authenticated submitter, trusted UTC submission time, deadline snapshot, computed late flag, and exactly one HTTPS link or private-file metadata source. PostgreSQL prevents updates and deletes to accepted versions. Phase 5A accepts the first version; Phase 5B adds version-scoped review and returned-version revisions.
- `supervisor_reviews` stores one immutable approval or return decision, its current supervisor reviewer, optional/required feedback, and UTC review timestamp for each version. `milestone_submissions.review_status` tracks the thread's current state; API history derives each version's status from its own review.
- `tasks` stores team-owned tasks with trimmed title, optional description, status (`todo`, `in_progress`, `done`), priority (`low`, `medium`, `high`), creator, active student member assignee, last updater, completion actor and timestamp, optional UTC deadline, bounded estimated minutes, nullable same-team milestone link, and nullable one-level same-team parent task link.
- `task_checklist_items` stores simple checklist items with task foreign key, nonblank item text, completion boolean, creator, completer, and server timestamps.
- `task_activities` stores immutable chronological audit entries tracking creation, assignment/reassignment, status transitions/reopening, metadata updates, checklist additions/modifications, comment additions, and attachment uploads. A PostgreSQL trigger prevents mutation or deletion.
- `task_comments` stores append-only comments posted by active team student members with trimmed content (1–2000 chars), author foreign key, and server UTC timestamps.
- `task_attachments` stores validated private file/image attachments with task foreign key, uploader foreign key, opaque 64-character storage key, original filename, bounded file size (<= 20 MiB), media type, and server UTC timestamps.
- `notification_read_receipts` stores persistent read receipts for derived deadline reminders with user foreign key, deterministic reminder UUID, and UTC read timestamp with primary key `(user_id, reminder_id)`.

Phase 7B derives deadline notifications dynamically on-the-fly and persists only read receipts, avoiding duplicate notification storage and maintaining perfect freshness across deadline adjustments.

### Tests and code checks

Database tests use a dedicated database whose name ends with `_test`; they never fall back to SQLite. The test fixture applies Alembic migrations and rolls each integration test back. Migration lifecycle checks use a temporary PostgreSQL schema. Set the test URL before running tests.

Run these commands from `src/backend` in PowerShell:

```powershell
$env:GRADTRACK_DATABASE_URL = "postgresql+psycopg://gradtrack:gradtrack@localhost:5432/gradtrack_test"
.\.venv\Scripts\python.exe -m pytest -m "not postgresql"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\ruff.exe check app tests migrations
.\.venv\Scripts\ruff.exe format --check app tests migrations
```

On macOS or Linux, use:

```shell
export GRADTRACK_DATABASE_URL="postgresql+psycopg://gradtrack:gradtrack@localhost:5432/gradtrack_test"
.venv/bin/python -m pytest -m "not postgresql"
.venv/bin/python -m pytest
.venv/bin/python -m pip check
.venv/bin/ruff check app tests migrations
.venv/bin/ruff format --check app tests migrations
```

The auth and milestone-rule unit tests run without PostgreSQL. The full suite, including registration, login, token, disabled-user, team and milestone authorization, timezone persistence, database-constraint, and migration integration tests, requires the dedicated `gradtrack_test` PostgreSQL database. CI uses a separate ephemeral PostgreSQL 16 service and a synthetic auth secret.

GitHub Actions runs the backend tests and lint/format checks on pushes and pull requests targeting `develop` or `main`, using an ephemeral PostgreSQL 16 service and retaining repository structure validation.
