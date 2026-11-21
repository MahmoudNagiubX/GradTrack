# GradTrack — Backend Integration & Local Demo Readiness

**For:** Antigravity CLI · user-selected Gemini Flash 3.8 High mode  
**Project:** SET312 GradTrack · university coursework / GitHub portfolio, **not** a production SaaS  
**Goal:** Prove the existing FastAPI + PostgreSQL + private local storage backend works **on the developer's Windows laptop**, with real HTTP interactions across the four mandatory course features and subsequent task/reminder features.  
**Type:** Verification, local setup, narrow bug fixing **only** — not a new product phase.  
**Do not start:** Phase 8, React, Flutter, cloud hosting, email/OTP, OCR, external notifications, or broad refactors.

## 1. Grounded starting facts — refresh before acting

As verified from the live GitHub repository on 20 November 2026:

- Repository: `https://github.com/MahmoudNagiubX/GradTrack`.
- **Latest feature branch:** `feature/GT-30-in-app-reminders` / PR **#12**, actual verified HEAD `3f6d760b5a6201739bdd52acf94ccbbc23766d15`.
- Exact-head CI: `https://github.com/MahmoudNagiubX/GradTrack/actions/runs/44767947594` — both repository check and backend test/lint jobs successful. Antigravity reported 290 passing tests in PostgreSQL 16 CI; that is **not proof of local PostgreSQL readiness**.
- Phase 7A bug-fix gate: PR **#11** head `cae0dad24ded11461a08d58c7b42cc0421333df6`, CI `https://github.com/MahmoudNagiubX/GradTrack/actions/runs/44762046465` successful. Upcoming-deadline calculation now excludes done tasks and anything farther than 14 days.
- **PRs #2 through #12 were all open and unmerged.** `develop` does not contain the complete backend. Human review and merge are **deferred, not waived**.
- Existing migrations through `gt30_0007`; private storage uses `GRADTRACK_PRIVATE_UPLOAD_DIR`, local PostgreSQL uses `GRADTRACK_DATABASE_URL`, and auth requires `GRADTRACK_AUTH_SECRET_KEY`.
- Backend auth has no public privileged-role creation endpoint. Demo supervisor/coordinator provisioning must be done through safe **dev-only synthetic fixture setup**, not a public role escalation endpoint.

Before work, independently check current branch, `git status --short`, remote, last commit, PRs and exact-head CI. If legitimate upstream updates occurred, use the actual verified head. Never guess SHA, claim a run tested a different commit, reset/clean/stash away unrelated changes, force push, or edit `main`/`develop`.

## 2. Required source reading (focused)

Read `AGENTS.md`, `docs/Graduation_Project_Tracker_Master_Plan.md` (instructor-required MVP and user journeys), `docs/project/definition-of-done.md`, `docs/project/git-workflow.md`, README setup section, `src/backend/app/{main,auth,teams,milestones,submissions,reviews,tasks,progress,notifications,submission_storage,config,database}.py`, and the current Alembic migrations and integration fixtures relevant to this check. Check applicable Jira issue references; this is an **integration checkpoint**, not permission to change their workflow states to Done.

Use the existing code and APIs. Revisit Smart Life Planner only if a real in-scope integration bug benefits from a **read-only** comparison; don't repeat a long irrelevant audit.

## 3. Scope / outcomes

Deliver **actual evidence** that the backend can run locally and demonstrate:

1. One local PostgreSQL database accepting migrations and persistent writes.
2. FastAPI starts with configured authentication and private file storage.
3. A synthetic student → team → coordinator-assigned supervisor → milestone → file/link submission → return → revision → approval journey, including the business rules.
4. A synthetic task → assignment → status → checklist → comment → private attachment/download journey.
5. Calendar, progress, supervisor progress, and student reminder endpoints from real persisted data.
6. Server restart retains database records, read receipts and private file access.
7. Basic security denials prevent another team's account or an unassigned supervisor from viewing, downloading or approving foreign work.
8. A concise reproducible Windows setup and demo walkthrough with observed status/result; no fake screenshots or fabricated clicks.

This is **NOT** a request for deployment, cloud storage, an antivirus service, Docker/Kubernetes, load testing, performance architecture, perfect coverage or a reimplementation of working backend modules.

## 4. Local Windows setup: detect first, do not invent installation state

### 4.1 Audit installed tools

Check OS, Python version and available venv, `psql`/`pg_isready`/PostgreSQL service availability, local port 5432, the current application DB, `alembic` revision state, and available disk space for small demo files. Do not assume PostgreSQL is installed just because CI used it. If absent, provide **precise short manual installation/start instructions** for official local PostgreSQL and pause only the blocked setup; do not silently install elevated services or alter firewall/security settings. Prefer existing installed PostgreSQL if usable.

### 4.2 Virtual environment and dependencies

From `src/backend`, reuse the existing `.venv` if healthy; otherwise follow README:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

Do not add dependencies without proven need. Do not change Python versions just to chase an unused production feature.

### 4.3 Two isolated local databases

Follow README for a **development database** (e.g., `gradtrack_dev`) and a dedicated `_test` database (e.g., `gradtrack_test`). Verify that the current instances are safe for synthetic tests. **Never drop or reset an existing database, delete personal files, or overwrite a user's data without express approval.** Avoid hardcoded actual secrets in tracked files, tests or terminal transcripts.

Set the correct URL in the active PowerShell environment and apply only a forward upgrade on the disposable or authorized development DB:

```powershell
$env:GRADTRACK_DATABASE_URL = "postgresql+psycopg://gradtrack:<LOCAL_PASSWORD>@127.0.0.1:5432/gradtrack_dev"
.\.venv\Scripts\alembic.exe current
.\.venv\Scripts\alembic.exe upgrade head
```

This example is a placeholder, not a real credential. Obtain settings from the laptop environment; don't print secrets. Verify the actual applied head is `gt30_0007` (unless a verified later migration legitimately exists). Run downgrades only on a **disposable test DB**, and observe the Phase 6B downgrade limitation/guard without attempting to alter real history.

### 4.4 Authentication and local private uploads

Create a random local-only signing key of adequate length using the README procedure. Set `GRADTRACK_PRIVATE_UPLOAD_DIR` to an absolute directory **outside the repository** on the local laptop, e.g. a separate private app-data folder; check the existing storage code's path/ACL and reparse-point requirements. Do **not** commit `.env`, logs, actual data, private files or keys. Use temporary synthetic PDF/TXT/image files only.

Start the API and verify both endpoints:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# GET http://127.0.0.1:8000/health -> {"status":"ok"}
# GET http://127.0.0.1:8000/health/database -> healthy only when PostgreSQL is connected
# http://127.0.0.1:8000/docs
```

No LAN exposure is required for this checkpoint; Flutter networking can be handled later. If the API starts but `/health/database` fails, stop claiming a successful local backend and diagnose the PostgreSQL configuration.

## 5. Real HTTP end-to-end demo — synthetic accounts only

**Use the actual FastAPI endpoints from OpenAPI/README.** Never invent endpoint URLs or request payloads and pretend they were executed. Test via HTTP, e.g., Python `httpx`, PowerShell `Invoke-RestMethod` or Swagger UI; database fixture inspection alone is insufficient. The local demo must include real PostgreSQL persistence.

### 5.1 Prepare synthetic roles safely

- Register two student accounts (e.g., student leader and second student) through `POST /auth/register`, then log in with `POST /auth/login` and verify `GET /auth/me`.
- Prepare exactly one **synthetic** supervisor and one **synthetic** coordinator through a safe **development-only database fixture/one-shot command** that uses the existing `User` ORM and password hash helper. No publicly exposed role creation route, no source-code change to relax authorization, no real student identifiers.
- Additional student from a second team and unassigned supervisor are needed only for negative test evidence. Use a disposable/demo dataset; never wipe existing accounts.
- If privileged fixture provisioning requires a code change, keep it small, explicitly dev-only, and non-public; do not install an admin panel.

### 5.2 Mandatory course journey

1. Student creates a team and becomes its leader; add a second existing student as a member.
2. Coordinator assigns the synthetic supervisor; student must be forbidden from doing the assignment.
3. Current supervisor or coordinator creates a named milestone with an offset-aware deadline. Student sees sorted milestones and derived deadline state.
4. Student uploads a small valid file as the first milestone submission. Verify submitter, timestamp, deadline snapshot, `is_late`, private storage metadata and authorized download. Repeat with a URL on a *different* milestone (one source per version).
5. Supervisor sees the latest version in assigned pending queue and **returns** with required feedback. Student sees feedback and the first version as returned.
6. Student submits the corrected **new version** (file or URL). Verify old version not edited, new current snapshot and review state pending.
7. Supervisor approves the new version; student sees both historical returned and newly approved version. Wrong/previous supervisor and coordinator cannot approve.
8. Demonstrate the late boundary with a deadline known to be before submission; use synthetic values and do not fake server clocks or timestamps.

### 5.3 Team productivity journey

1. Leader creates tasks, assigns member, sets priority, due time and optional milestone.
2. Member moves assigned task `todo → in_progress → done`; leader can reopen it. Confirm actual completion actor and chronological activity.
3. Leader adds checklist item; assigned member marks it complete. Create a one-level subtask and read it in task detail.
4. Member posts a comment and uploads a tiny valid PDF/TXT/image using the **same configured private storage**. Team viewer downloads it; cross-team account cannot. Confirm filename, media type, author/time and activity.
5. Fetch `/teams/{team_id}/calendar?start_at=...&end_at=...` with properly URL-encoded offset-aware date parameters. Confirm tasks/milestones appear within the half-open window.
6. Fetch `/teams/{team_id}/progress` and `/supervisor/teams/progress`. Confirm counts match actual persisted tasks and reviews, including upcoming items in the <=14-day window **excluding completed tasks**.
7. Fetch `/notifications` as the student, confirm assigned incomplete-task and actionable milestone reminders, then POST `/notifications/{id}/read`. Verify `unread_only=true`, and that changing a deadline invalidates an old reminder rather than keeping it stale. Use the existing 7-day rules; no push service.

### 5.4 Restart and persistence

Stop Uvicorn normally, restart it with the same database and upload directory, log in again, and verify team, task, milestone, revisions, comments, actual files, supervisor decisions and read receipts still persist. This is essential for a laptop-only demo.

### 5.5 Negative checks (at minimum)

- No/invalid token: 401 on protected endpoints.
- Wrong team: no team/task/submission data or attachment download.
- Wrong/unassigned supervisor: no approval and no assigned team progress.
- Student role cannot create supervisor milestones or reviews.
- Unsupported/malformed/oversize file rejected; private file path never exposed.
- No stale/deleted-deadline reminders or false unread state after deadline change.

Record expected status, observed status, and response shape. Do not log password/token/full private file bytes.

## 6. Regression, CI, and bugs

- Run non-PostgreSQL suite locally and **full** PostgreSQL integration suite against dedicated `_test` database if the laptop has PostgreSQL. The exact local counts must be observed, not copied from GitHub CI.
- Run `ruff check app tests migrations`, `ruff format --check app tests migrations`, `python -m pip check`, `git diff --check` and Alembic revision inspection.
- Keep the latest PR #12 exact-head CI as established baseline, but if changing code push to **a new bounded fix branch** based on the current verified Phase 7B head, not to shared branches. Open a stacked PR if code changes warrant it; report exact pushed SHA and **new** successful CI.
- If a genuine demo-blocking defect appears, fix only the proven issue with a regression test. No architectural cleanup or broad security/deployment improvements.
- If a local setup failure is environmental (e.g., PostgreSQL not installed or no Windows ACL), give the user exact manual steps and clearly label the demo **BLOCKED**, even though GitHub CI is green.

## 7. Deliverable and acceptance gate

Provide a short factual Markdown report (either in the CLI response or one existing `docs/developer-tasks/` location if the developer approves adding a file) with:

```text
Actual repository branch and head:
PR #2–#12 statuses and human-review blockers:
Operating system, Python and PostgreSQL versions actually observed:
PostgreSQL local service and migrated database: PASS / FAIL / BLOCKED
Authentication key and private upload path configured: YES / NO (no values)
API health AND database health actual HTTP status:
Full HTTP student/supervisor journey: PASS / PARTIAL / BLOCKED, with evidence
Task/comment/attachment/calendar/progress/reminders journey: PASS / PARTIAL / BLOCKED
Cross-team authorization checks and file persistence after restart:
Unit tests local / PostgreSQL integration tests local / exact-head GitHub CI:
In-scope bugs found/fixed, regression tests and any new PR:
Manual steps the developer must perform (only if necessary):
READY_FOR_REACT_WEB: YES / NO; why:
```

**Important:** `READY_FOR_REACT_WEB: YES` means the existing FastAPI endpoints and local demo setup work. It does **not** imply PR approval/merge, completed university Sprint Review, finished profile/avatar, all planned product features, a deployed system or a production-ready security posture.

**Stop after this checkpoint**. Do not implement React/Flutter, Phase 8, cloud infrastructure or broad refactors. Human PR review/merge remains a separate pending requirement and must not be claimed as accomplished.
