# Phase 7B Execution Report: In-App Deadline Reminders (Backend)

> **Task Key:** GT-30 ([Receive Deadline Reminders](https://mahmoudnagiub.atlassian.net/browse/GT-30))  
> **Specification:** `docs/developer-tasks/GradTrack_Phase7B_InApp_Reminders_Antigravity.md`  
> **Operating Rules:** `AGENTS.md` & Phase 7B Approved Rules P1–P6  
> **Gate 0 Verified Base Commit:** `cae0dad24ded11461a08d58c7b42cc0421333df6` (PR #11 Head, CI Run `44762046465`)  
> **Feature Branch:** `feature/GT-30-in-app-reminders`  

---

## 1. Gate 0 Progress Bug Fix (PR #11)

- **Root Cause & Scope:** `_compute_team_progress` in `src/backend/app/progress.py` included completed (`done`) tasks in `upcoming`, and did not restrict upcoming task and milestone items to the promised 14-day window (`now <= due_at <= now + 14 days`).
- **Files Changed:**
  - `src/backend/app/progress.py`: Added `max_upcoming_utc = now_utc + timedelta(days=14)`, filtered out `task.status == "done"`, and enforced `now_utc <= due_at <= max_upcoming_utc` for both tasks and milestones.
  - `src/backend/tests/test_progress.py`: Added focused regression test `test_team_progress_upcoming_deadlines_boundary_and_done_exclusion` checking incomplete tasks due today, completed future tasks (excluded), exact 14-day boundaries, 14 days + 1 microsecond (excluded), past items (excluded), and student/supervisor parity.
- **Commit:** `cae0dad`: `fix(GT-31): exclude done and distant deadlines from upcoming`
- **PR #11 Updated Head SHA:** `cae0dad24ded11461a08d58c7b42cc0421333df6`
- **Gate 0 CI Run:** [Run 44762046465](https://github.com/MahmoudNagiubX/GradTrack/actions/runs/44762046465) (Passed in 50s, **277 passed in 11.56s on PostgreSQL 16**, all checks passed).

---

## 2. Phase 7B Starting Head & Branch Discipline

- **Starting Head:** `cae0dad24ded11461a08d58c7b42cc0421333df6` (PR #11 verified head).
- **Branch Name:** `feature/GT-30-in-app-reminders` (new stacked feature branch, zero commits to `develop` or `main`).
- **Worktree State:** Clean worktree.

---

## 3. Approved Product Rules (P1–P6) Compliance

- **P1 — Actors and Sources:** Accessible strictly by active student members. Tasks are scoped exclusively to those currently assigned to the calling student in their active teams. Milestones are scoped to shared team milestones where action is needed (`not_submitted` or `returned`). Submissions that are `approved` or `pending_review` produce no student reminder. Supervisors and coordinators receive HTTP 403 Forbidden.
- **P2 — Deadline States & 7-Day Window:** Single 7-day window for tasks and milestones. `due_soon` when `now <= due_at <= now + 7 days`. `overdue` when `due_at < now`. At exact deadline (`due_at == now`), it is classified as `due_soon`. Deadlines > 7 days in the future are ignored.
- **P3 — Local Pull-Based Notification Center:** Notifications are derived dynamically on client request (`GET /notifications`). Zero background daemons, Celery/cron workers, Redis, push notifications, or WebSockets.
- **P4 — Persisted Read Receipts Only:** Only read receipts are persisted in `notification_read_receipts` table with composite key `(user_id, reminder_id)`.
- **P5 — Changed Deadlines / Stale Notices:** Reminder IDs are derived deterministically using `uuid5` from `source_kind + source_id + UTC due_at + reminder_kind`. Changing source deadlines naturally invalidates old reminder IDs and generates fresh unread notices.
- **P6 — API / Permissions:** Students can only read and mark their own visible reminders. Unauthorized, foreign-team, and stale reminder marks return HTTP 404. Non-students receive HTTP 403.

---

## 4. Smart Life Planner Audit

Inspected local Smart Life Planner reference code read-only at `C:\Users\mahmo\Desktop\Vscode\Smart Life Planner` (revision `f44c4c7`):
- **REUSE:** None directly. Smart Life Planner uses async SQLAlchemy, a persistent `reminders` table with background delivery, and mobile local notifications plugins.
- **ADAPT:** Conceptual stale reminder invalidation upon deadline/target change (implemented in GradTrack purely on-the-fly via deterministic UUID5 hashing, requiring zero active background invalidation queries).
- **REFERENCE:** Invalidation semantics upon target mutation or deadline changes, and timezone normalization.
- **REJECT:** Heavy `Reminder` table, Celery/scheduler queues, async SQLAlchemy, personal prayer/habit targets, snooze intervals, persistent occurrence counters, and email/push fallback channels.

---

## 5. Schema, Migration, Endpoints & Sample Responses

### 5.1 Models & Migration
- **Model:** `NotificationReadReceipt` in `src/backend/app/models.py`:
  - `user_id`: UUID, FK to `users.id` (CASCADE), primary key
  - `reminder_id`: UUID, primary key
  - `read_at`: DateTime(timezone=True), server_default=now()
- **Migration:** `src/backend/migrations/versions/gt30_0007_notification_reads.py`:
  - `revision = "gt30_0007"` (down_revision = `"gt28_0006"`)
  - Creates `notification_read_receipts` table with composite primary key `(user_id, reminder_id)` and index on `user_id`.
  - Downgrade cleanly drops the table and index.

### 5.2 Endpoints
- `GET /notifications`: Lists active due-soon and overdue reminders for the student.
- `GET /notifications?unread_only=true`: Filters out reminders with existing read receipts.
- `POST /notifications/{reminder_id}/read`: Idempotently marks a currently active reminder as read.

### 5.3 Sample Response
```json
[
  {
    "id": "e6745163-4876-5fae-9d2a-a91d846c9c6f",
    "kind": "task_due_soon",
    "source_id": "8bb38f82-a9b8-466d-96f7-34757c918663",
    "team_id": "a933ff22-441d-4402-b258-01cae5f156d9",
    "title": "Implement authentication endpoints",
    "due_at": "2026-12-15T15:00:00Z",
    "is_read": false,
    "read_at": null
  }
]
```

---

## 6. Verification & Test Evidence

### 6.1 Local Tests
- **Ruff:** `ruff check app tests migrations` passed with 0 errors.
- **Ruff Format:** `ruff format --check app tests migrations` passed with 0 errors.
- **Bytecode & Dependencies:** `python -m compileall -q app migrations tests` and `python -m pip check` passed.
- **Git Diffs:** `git diff --check` passed with 0 errors.
- **Unit Test Suite:** `pytest -m "not postgresql"` executed 129 selected tests:
  - **128 passed**, 1 skipped (Windows symlink test), 161 deselected.
  - Added `tests/test_notification_rules.py` (5 unit tests for boundary classification, UUID5 determinism, attribute variation, Cairo timezone normalization, and schema validation).

### 6.2 PostgreSQL Integration Suite (`tests/test_notifications.py` & `tests/test_migrations.py`)
- Added 7 integration tests in `tests/test_notifications.py`:
  1. `test_notifications_active_student_assigned_task_and_team_milestone`: Per-assignee task isolation and shared milestone visibility.
  2. `test_notifications_milestone_review_states_and_done_tasks`: Milestone review states (`not_submitted` & `returned` shown; `pending_review` & `approved` hidden) and completed task hiding.
  3. `test_notifications_overdue_and_due_soon_boundaries`: Boundary tests for exact deadline (`due_soon`), overdue, exact 7-day cutoff, and > 7 days exclusion.
  4. `test_notifications_mark_read_and_unread_filter`: Read receipt persistence, idempotency, and `unread_only=true` filter.
  5. `test_notifications_deadline_change_invalidates_stale_reminder`: Stable ID mutation upon deadline change, automatic staleness, and 404 rejection of outdated IDs.
  6. `test_notifications_authorization_and_isolation`: Role enforcement (403 for supervisor, coordinator, inactive student), cross-team isolation, and 401 unauthenticated.
  7. `test_notifications_cross_phase_e2e`: Full multi-phase lifecycle test covering registration, team creation, task assignment, milestone creation, submission, review return, review approval, task completion, and read receipts.
- Added migration test in `tests/test_migrations.py`:
  - `test_phase7b_notification_read_receipts_migration_and_downgrade`: Verifies clean upgrade, row insertion, downgrade to `gt28_0006`, data preservation of other tables, and re-upgrade to `head`.

---

## 7. Git & GitHub Evidence

- **Base Commit:** `cae0dad24ded11461a08d58c7b42cc0421333df6` (PR #11 Head)
- **Head Commit:** `<WILL_BE_UPDATED_AFTER_COMMIT>`
- **Pull Request:** `<WILL_BE_UPDATED_AFTER_PR>`
- **GitHub Actions CI Run:** `<WILL_BE_UPDATED_AFTER_CI>`

---

## 8. Limitations & Operating Discipline

- **No Active Push/Background Daemons:** Reminders are retrieved upon active client pull (`GET /notifications`). No push notifications, Celery/cron tasks, or WebSockets run when the app is closed.
- **Frontend Deferred:** React and Flutter UI screens are out of scope for this backend task.
- **Jira Status:** GT-30 remains **In Progress / In Review** (not marked Done).
- **PR Status:** Stacked PR open against `develop`; no PRs merged.
