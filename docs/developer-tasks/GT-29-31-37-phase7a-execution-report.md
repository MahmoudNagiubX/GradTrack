# Phase 7A Execution Report: Timeline / Calendar Data & Progress Dashboards (Backend)

> **Task Keys:** GT-29 (Timeline Calendar Feed), GT-31 (Team Progress Dashboard), GT-37 (Supervisor Teams Progress Overview)  
> **Specification:** `docs/developer-tasks/GradTrack_Phase7A_Timeline_Dashboards_Antigravity.md`  
> **Operating Rules:** `AGENTS.md` & Phase 7A Approved Rules R1–R6  
> **Base Commit:** `f0065c12d3fd3afd271e44c2edaab2aa91a53237` (PR #10 Head, Verified CI Run `44751895634`)  
> **Feature Branch:** `feature/GT-29-31-37-timeline-progress`  

---

## 1. Executive Summary

Phase 7A implements the read-side backend foundations for GradTrack's unified timeline calendar and student/supervisor progress dashboards:
1. **GT-29 (`GET /teams/{team_id}/calendar`):** Unified chronological feed of tasks and milestones in a half-open window `[start_at, end_at)` (maximum window of 93 days), returning a discriminated union on `kind`.
2. **GT-31 (`GET /teams/{team_id}/progress`):** Comprehensive progress metrics for a team, including task lifecycle counts, overdue count, breakdown by assignee, milestone review and deadline counts, late submission count, and upcoming deadlines within 14 days.
3. **GT-37 (`GET /supervisor/teams/progress`):** Supervisor portfolio view returning progress summaries for all teams currently assigned to the calling supervisor, ordered alphabetically by team name.

All metrics are derived dynamically from existing database tables on query execution (**Rule R1: No New Tables or Migrations**), preserving 100% semantic consistency across student team and supervisor views via a shared calculation engine.

---

## 2. Upstream Verification & Corrections

- **Phase 6B PR:** PR #10 (`feature/GT-28-task-collaboration`) targeting `develop`.
- **Phase 6B Head SHA:** `f0065c12d3fd3afd271e44c2edaab2aa91a53237`.
- **Phase 6B CI Run:** `44751895634` (Passed, 265 tests passing on PostgreSQL 16).
- **Execution Report Correction:** Updated `docs/developer-tasks/GT-28-phase6b-execution-report.md` to reference verified head commit `f0065c12d3fd3afd271e44c2edaab2aa91a53237` and CI run `44751895634`.
- **Phase 6B Migration Downgrade Edge:**
  - *Investigation:* During downgrade of `gt28_0006_task_collaboration.py` to `gt26_27_0005`, recreating the check constraint on `task_activities.activity_type` failed if collaboration activities (`comment_added`, `attachment_uploaded`) existed in the database.
  - *Fix:* Added an explicit check before dropping columns and altering check constraints in `gt28_0006_task_collaboration.py:downgrade()`. If collaboration activities exist, it raises a safe, informative `RuntimeError` rather than corrupting check constraints or silently destroying audit history.
  - *Test Verification:* Added regression assertion in `src/backend/tests/test_migrations.py`.

---

## 3. Smart Life Planner Inspection & Architectural Reuse

Inspected the Smart Life Planner reference codebase at `C:\Users\mahmo\Desktop\Vscode\Smart Life Planner` (commit `f44c4c7`):
- **`services/dashboard.py` & `models/dashboard.py`:** Inspected aggregation patterns. Rejected personal habit metrics, prayer times, and subjective daily scoring as irrelevant to academic graduation project tracking.
- **`services/project_timeline_service.py`:** Evaluated timeline and overdue calculation patterns. Reused and adapted:
  - Exact overdue calculation: `due_at < now and status != 'done'` (exact equality `due_at == now` is not overdue).
  - Offset-aware UTC normalization helper `_as_utc(dt)`.
  - Rejected: Complex CPM/PERT critical path algorithms, Slack/Discord notification webhooks, and client-side Gantt dragging state (violates R1/R6).
- **`services/pomodoro_progress.py`:** Inspected Pomodoro tracking; rejected in its entirety as out of scope.

---

## 4. Implemented Endpoints & Business Logic

### 4.1 GT-29: Unified Timeline Calendar Feed (`GET /teams/{team_id}/calendar`)
- **Query Parameters:**
  - `start_at`: Required ISO 8601 offset-aware timestamp.
  - `end_at`: Required ISO 8601 offset-aware timestamp.
- **Boundary Semantics (Rule R2):**
  - Half-open window: `[start_at, end_at)` (inclusive of `start_at`, exclusive of `end_at`).
  - Validation: Requires `start_at < end_at` and `end_at - start_at <= 93 days` (HTTP 422 if invalid).
  - Tasks with `due_at = NULL` are omitted from the calendar.
- **Ordering:** Chronological by `due_at` ascending, with item ID as tie-breaker.
- **Discriminated Union Schema (`kind`):**
  - `kind="task"`: `CalendarTaskItem` (id, team_id, title, due_at, status, priority, assignee_id, milestone_id).
  - `kind="milestone"`: `CalendarMilestoneItem` (id, team_id, title, due_at, deadline_status, review_status).
- **Authorization:** Active team members, currently assigned supervisor, or programme coordinator. Unaffiliated accounts receive HTTP 404 (preventing team enumeration).

### 4.2 GT-31: Team Progress Dashboard (`GET /teams/{team_id}/progress`)
- **Derived Progress Structure:**
  - `team_id`, `team_name`, `as_of` (UTC snapshot).
  - `tasks`: `TaskProgressCounts` (`total`, `todo`, `in_progress`, `done`, `overdue`).
  - `tasks_by_assignee`: Array of `AssigneeTaskProgress` (`user_id`, `display_name`, `total`, `todo`, `in_progress`, `done`, `overdue`), sorted by display name.
  - `milestones`: `MilestoneProgressCounts`:
    - Review lifecycle: `not_submitted`, `pending_review`, `returned`, `approved`.
    - Planning deadline status: `scheduled`, `due_soon` (within 7 days), `overdue` (derived via existing `deadline_status` domain helper).
  - `late_submissions`: Count of milestones whose latest submitted version was submitted after the deadline snapshot (`latest_version.is_late is True`). Avoids overcounting historical revisions.
  - `upcoming`: Unified list of tasks and milestones due within 14 days (`now <= due_at <= now + 14 days`), excluding completed tasks (`done`), sorted by `due_at` ascending.
- **Authorization:** Active team members, currently assigned supervisor, or coordinator.

### 4.3 GT-37: Supervisor Teams Progress Overview (`GET /supervisor/teams/progress`)
- **Portfolio Scoping (Rule R4):**
  - Accessible strictly by authenticated, active supervisors (`current_user.system_role == "supervisor"`).
  - Programme coordinators and students receive HTTP 403 Forbidden.
  - Queries teams joined with `supervisor_assignments` where `supervisor_id == current_user.id`.
  - Reassigned supervisors immediately lose visibility to former teams.
  - Returns `list[TeamProgressSummaryResponse]`, ordered alphabetically by `team_name` (secondary tie-breaker `team_id`).

---

## 5. Verification & Testing

### 5.1 Local Verification
- **Code Style & Linting:** `ruff check app tests migrations` passed with 0 errors.
- **Formatting:** `ruff format --check app tests migrations` passed with 0 errors.
- **Bytecode Compilation:** `python -m compileall -q app migrations tests` passed.
- **Dependency Integrity:** `python -m pip check` reported no broken dependencies.
- **Git Diffs:** `git diff --check` reported 0 issues.
- **Unit Tests:** `pytest -m "not postgresql"` executed 124 tests:
  - 123 passed, 1 skipped (Windows symlink test), 152 deselected.
  - New schema tests: `tests/test_progress_schemas.py` (7 tests covering valid serialization and discriminated union validation).

### 5.2 PostgreSQL Integration Suite (`tests/test_progress.py`)
Added 10 comprehensive integration and authorization tests:
1. `test_calendar_mixed_tasks_and_milestones`: Verifies interleaved tasks and milestones, ordering, and field mapping.
2. `test_calendar_exact_half_open_boundaries_and_timezones`: Verifies half-open interval `[start_at, end_at)` and Cairo timezone offset conversions.
3. `test_calendar_validation_and_range_limits`: Validates inverted ranges, identical start/end, > 93 day limits, and naive datetime rejection.
4. `test_calendar_authorization_and_isolation`: Verifies team member access, assigned supervisor access, coordinator access, cross-team 404 isolation, and student 404 on non-member teams.
5. `test_team_progress_empty_team`: Verifies clean 0-counts and empty lists for a team with no tasks or milestones.
6. `test_team_progress_tasks_lifecycle_and_overdue_boundaries`: Tests task status breakdown, assignee grouping, and exact boundary condition for overdue (`due_at == now` is not overdue).
7. `test_team_progress_milestones_and_late_submissions`: Tests milestone status, late submission counting, and 14-day upcoming list filter.
8. `test_supervisor_teams_progress_multiple_teams`: Verifies supervisor portfolio view with multiple assigned teams, alphabetical sorting, and independent metrics.
9. `test_supervisor_teams_progress_reassignment_and_empty`: Verifies immediate loss of team visibility upon reassignment and empty array for unassigned supervisors.
10. `test_supervisor_teams_progress_authorization`: Verifies 403 Forbidden for coordinators and students, and 401 for unauthenticated calls.

---

## 6. Git & GitHub Evidence

- **Branch Name:** `feature/GT-29-31-37-timeline-progress`
- **Base Commit:** `f0065c12d3fd3afd271e44c2edaab2aa91a53237`
- **Head Commit:** `<WILL_BE_UPDATED_AFTER_COMMIT>`
- **Pull Request:** `<WILL_BE_UPDATED_AFTER_PR>`
- **GitHub Actions CI Run:** `<WILL_BE_UPDATED_AFTER_CI>`

---

## 7. Known Limitations & Out of Scope (Phase 7A)

- **Frontend Implementations:** No React or Flutter screens (backend API only).
- **In-App Reminders (Phase 7B):** Reminders, notification badges, and background jobs are excluded per Rule R6.
- **Calendar Filtering:** Currently returns all team items within the date window; client-side filtering can narrow by assignee or milestone.
- **Multi-Programme Support:** Coordinator global visibility remains pilot-scoped until `Programme` entity is introduced in future phases.
