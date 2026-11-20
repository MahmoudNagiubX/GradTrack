# GradTrack — Phase 7B: In-App Deadline Reminders (Antigravity CLI)

**Date:** 20 November 2026  
**Repository:** `MahmoudNagiubX/GradTrack`  
**Jira:** [GT-30 — Receive Deadline Reminders](https://mahmoudnagiub.atlassian.net/browse/GT-30)  
**Agent:** Antigravity CLI, user-selected Flash 3.8 High  
**Delivery:** Backend only — FastAPI, synchronous SQLAlchemy, PostgreSQL 16, Alembic. **Local laptop / university demo**, not production SaaS.  
**Implementation phases in this document:** Gate 0 (small Phase 7A bug fix) → Phase 7B (GT-30 only).  
**Required output:** New task branch and a stacked PR targeting `develop`; tests, exact-head GitHub Actions CI, one factual execution report; **no auto-merge**.

> Read root `AGENTS.md`, `docs/Graduation_Project_Tracker_Master_Plan.md` (§§4, 5.2–5.7 and delivery priorities), `docs/project/git-workflow.md`, `docs/project/definition-of-done.md`, current GT-30 Jira description, README, source files and tests before making any changes. The repository's Master Plan and approved instructions govern scope.

## 0. Verified starting facts — refresh against live GitHub before editing

- [PR #11 — Phase 7A](https://github.com/MahmoudNagiubX/GradTrack/pull/11) was **open/unmerged** at exact branch head `14987f7776dc471f37d024bced74351b5a861e74`.
- [GitHub Actions run 44758484149](https://github.com/MahmoudNagiubX/GradTrack/actions/runs/44758484149) succeeded on this exact SHA; Phase 7A implementation report claims **276 tests passed** against PostgreSQL 16. Do not assume the number is still current after changes.
- PRs **#2 → #3 → #4 → #5 → #6 → #7 → #8 → #9 → #10 → #11** were all open and stacked, targeting `develop`. Human approvals and merges are **deferred, not waived**. No agent may merge them or mark Jira `Done`.
- `src/backend/app/progress.py` provides `GET /teams/{team_id}/calendar`, `GET /teams/{team_id}/progress`, and `GET /supervisor/teams/progress`. `src/backend/app/milestones.py` already defines the 7-day `deadline_status` function. Tasks live in `src/backend/app/tasks.py`; milestone submissions/reviews live in the existing `submissions.py`/`reviews.py`. Current migration head: `gt28_0006` (no new migration in Phase 7A).
- Existing private storage for uploads remains local to the operator's computer. Phase 7B does not require any new storage provider or credentials.

**Mandatory preflight:** `git status --short`, branch/remotes, fetch remote refs, verify PR #11 exact head and CI, inspect `AGENTS.md`, relevant models/routes/tests, and any uncommitted work. Do not reset/clean/stash/discard user changes, rewrite history, force-push, change `main` or `develop`, or invent a GitHub reviewer identity.

## 1. Gate 0 — fix a confirmed Phase 7A upcoming-list bug **before** Phase 7B

The current `_compute_team_progress` implementation in `src/backend/app/progress.py` builds `upcoming` from **all** future due dates and **includes completed (`done`) tasks**. The Phase 7A execution report promises upcoming work **within 14 days**, excluding completed tasks. Existing integration tests do not explicitly assert those two requirements.

1. Work on the **existing** `feature/GT-29-31-37-timeline-progress` branch for this isolated fix, if its remote head and clean worktree permit it; never modify `develop`. If the branch has changed, inspect the new code before acting.
2. Preserve intended current status counts: completed tasks should still count as `done`, but must **not** be shown as upcoming work.
3. Include task/milestone deadlines only when `now <= due_at <= now + timedelta(days=14)`; future dates after day 14 are excluded. Keep current intended deterministic chronological order and reasonable top-10 display cap, if that cap is documented and consistent with UI semantics.
4. Add a focused real-PostgreSQL regression test with an incomplete task due today, a completed future task, tasks/milestones exactly at 14 days, a due date 14 days + 1 microsecond away, and date values in the past. Include student/supervisor visibility regression where relevant.
5. Run existing tests and lint; commit a **small** `fix(GT-31): exclude done and distant deadlines from upcoming`; push to **PR #11's feature branch only**; confirm new exact-head CI passed. Update the Phase 7A report/README only if needed for truthful evidence. If CI fails or branch conflict exists, **STOP and report**; do not start GT-30 yet.
6. Create the Phase 7B branch **only from that newly verified Phase 7A head**. Do not use the old SHA after Gate 0.

This is a confirmed bounded regression correction, **not** permission to refactor Phase 7A or broaden its features.

## 2. Proposed Phase 7B product rules — approved only when PO accepts in startup message

**P1 — Actors and sources:** In-app reminders go to *active student members*, including team leaders. For tasks, show only tasks **currently assigned to that student**, in a team where they still have membership. For milestones, show shared team milestones where action is still needed: **not submitted** or **returned**. Do not remind students about approved submissions or work already **pending supervisor review**. Supervisors have the separate current pending-review inbox; coordinator and supervisor reminder inboxes are out of GT-30 scope. No public access.

**P2 — Deadline states:** Use a single **7-day** due-soon window for both task and milestone reminders, aligned to existing Phase 4 semantics. `due_soon` when `now <= due_at <= now+7days`; `overdue` only when `due_at < now`; at the exact deadline it is still due-soon. Ignore tasks with no due date; ignore `done` tasks. Dates are compared as offset-aware UTC instants using a testable clock. No reminder for a future deadline beyond 7 days. An overdue actionable item remains visible until it is completed, approved, sent back to review as appropriate, or deadline moved.

**P3 — Local pull-based notification center:** Provide one lightweight authenticated API to retrieve reminders **when the app opens or refreshes**. Do **not** add cron, Celery, Redis, scheduled workers, email, push notifications, cloud dependencies, SMS, WebSockets, or OS notifications. Do not claim a popup arrives when the server/client is not running. Clients can refresh/poll as needed.

**P4 — Persist read receipts only:** Reminder content and current status are **derived from existing task, milestone, submission and team data**, not duplicated in a separate notification table. Add **one minimal table** for `(user_id, reminder_id, read_at)` with a uniqueness constraint. `is_read` is derived from this receipt. The API must reject attempts to mark IDs not currently visible to the caller.

**P5 — Changed deadlines / stale notices:** Use a stable deterministic reminder ID based on `source_kind + source_id + current UTC due_at + reminder_kind`. Thus changing the source deadline automatically removes the old reminder from the live list, and the new current reminder has a new ID; overdue can become due-soon when a deadline is extended. Old read receipts may be retained without being shown; no cleanup job is needed for the demo. A past read receipt must never cause another user's reminder to appear read. No duplicates across repeated GET requests.

**P6 — API/permissions:** Read-only students may read their own generated reminders; only the same student may mark their own reminder as read. Validate current team membership and task assignment or milestone applicability server-side, including after reassignment and team membership changes. A former team member should no longer see that team's reminders. Do not disclose private team titles to unauthorized users. Non-student roles receive 403; unauthenticated 401, following existing auth conventions.

These six product choices are a scoped proposed implementation for the university demo; **they are not automatically approved by the existence of this file**. If startup prompt does not explicitly approve P1–P6, ask first. A conflicting Master Plan/Jira rule requires a concrete human decision before implementing affected behavior.

## 3. GT-30 user story and acceptance contract

**Jira user story:** As a team member, I want to receive reminders before important deadlines so that I have time to finish my work.

Exact Jira acceptance checks:
1. The system can remind a user before a task or milestone deadline.
2. A user can view the reminder in the app.
3. A changed deadline does not leave an incorrect reminder.

**Backend interpretation:** A React/Flutter client can call the notifications API to display reminders; frontend screens are a separate phase. Do not call the user story fully accepted at course level until an actual in-app UI demonstrates it. Current Jira story-point `3` is a **draft**, not a confirmed team estimate; do not change it.

## 4. Minimal API contract

| Method | Proposed endpoint | Authorized behavior |
|---|---|---|
| `GET` | `/notifications` | Current student's actionable due-soon and overdue task/milestone reminders, including read flags, sorted predictably |
| `GET` | `/notifications?unread_only=true` | Same source scoped to caller, filtered by `is_read=false` |
| `POST` | `/notifications/{reminder_id}/read` | Mark a currently visible reminder as read, idempotently |

**Example response (synthetic):**

```json
[
  {
    "id": "5d68c15e-f1e6-544d-81ad-9ba10ff2d9a5",
    "kind": "task_due_soon",
    "source_id": "a44d2b48-4a19-4d95-893e-55d86e109889",
    "team_id": "b0d047ca-3b84-4a48-a2e8-95a0644fc0e1",
    "title": "Finish SRS diagrams",
    "due_at": "2026-12-01T15:00:00Z",
    "is_read": false
  }
]
```

IDs above are **illustrative**, never hard-code test fixtures from them. Allowed `kind` values: `task_due_soon`, `task_overdue`, `milestone_due_soon`, `milestone_overdue`. Return ISO-8601 UTC. Empty inbox must be `[]`. Identifiers are not bearer tokens; security is enforced by the existing JWT and resource ownership checks.

Optional: return `read_at` only if it helps actual clients; do not build a second statistics/count endpoint when React can count unread entries from this response.

## 5. Data / implementation strategy (minimal)

- New Alembic revision **after** current actual migration head `gt28_0006`, e.g. `gt30_0007_notification_reads.py`, with a small `notification_read_receipts` table: `user_id` FK to `users`, `reminder_id` UUID, timezone-aware `read_at`; unique pair `(user_id, reminder_id)` (composite PK acceptable). No redundant task/milestone duplication or extra task ownership model.
- Add a small `app/notifications.py` route/domain module, or integrate into an appropriate existing module if that would be clearer. Register router in `main.py`, schemas in `schemas.py`, model in `models.py`, tests in `tests/`.
- Use existing `TeamMembership`, `Team`, `Task`, `Milestone`, `MilestoneSubmission`, `User`, `CurrentUser` and session dependencies. Query only actually accessible teams/resources; avoid creating public global notification listings.
- Use built-in Python `uuid.uuid5` with a fixed project-specific namespace plus canonical source/type/deadline data; no new dependency. Derive current due-soon/overdue state each request. If an equivalent safe identifier utility is already in the repo, reuse it instead.
- `POST /read`: recompute visible reminders server-side and ensure the posted ID belongs to current user's **current** list before persisting receipt. Repeat POST returns success without duplicate rows; concurrent calls honor DB uniqueness constraint.
- Avoid unnecessary custom scheduler/cache/queue, filesystem storage changes, duplicate milestone-status calculations or comprehensive event-sourcing. Existing comments/submissions remain unchanged.
- Local PostgreSQL is the actual database. Retain existing migration and test fixture conventions; no SQLite stand-in and no new external service required.

## 6. Required tests

**Unit tests (pure rules):**
- Seven days + 1 microsecond is not due-soon; exactly seven days is; at exact deadline is due-soon; 1 microsecond later is overdue.
- UTC normalization for Cairo `+02:00` and `Z` representations; naive timestamps rejected consistently if accepted through inputs.
- Stable ID for unchanged source/time/kind; changed deadline changes ID; due-soon→overdue changes ID; repeated evaluations produce no duplicate inbox entries.

**PostgreSQL integration:**
- Active member gets assigned task reminder and actionable team milestone reminder; another member gets milestone but not someone else's assigned-task reminder.
- Completed task, task without due date, approved milestone, and milestone pending review produce **no** student reminder.
- Returned milestone becomes actionable; approved version removes it; task status `done` removes assigned-task reminder.
- When deadline changes, the outdated reminder disappears and current one appears only when within window or overdue; changing to >7 days removes due-soon reminder.
- Unread reminders start unread; mark-read remains read on repeated GET; repeated/concurrent marks do not duplicate receipts.
- No authorization leakage to other-team member, removed student, inactive user, former supervisor or coordinator.
- Nonexistent/stale/foreign reminder ID cannot be marked read, and does not create receipt or leak details.
- Empty team/no actionable work returns `[]`; sorting consistent on ties.
- Upgrade/downgrade in disposable PostgreSQL test schema, existing task/milestone/review rows preserved.
- Full regressions: Phase 0–7A auth, team, submissions, file storage, review approval, task activity/comments/attachments, calendar/progress, 7A fixed `upcoming` behavior.

**Cross-phase E2E:** register two students; create team; assign task; coordinator assigns supervisor; supervisor creates milestone; fetch reminders; mark one read; update deadline; confirm stale reminder gone; submit milestone; verify pending review hides it; return, check reminder; approve, check hidden; close task, check hidden; ensure foreign student/old member cannot read/mark other team's notifications.

## 7. Repository quality, Agile and Smart Life Planner audit

1. Audit relevant local `C:\Users\mahmo\Desktop\Vscode\Smart Life Planner` code **read-only** (previously `f44c4c7fe97a53d03e4df07bbbf42feaf432f9a1`): reminder models/routes/due date tests. Classify REUSE / ADAPT / REFERENCE / REJECT, with compatibility and effort. Don't copy async ORM/auth, email fallbacks, credentials, `.env`, user data, scheduler complexity or irrelevant code.
2. Every task should be directly testable and relevant to the course demo. User has explicitly chosen local laptop operation; no cloud storage, production hardening projects or third-party credentials.
3. Do not edit applied migrations except Gate 0's already-included downgrade guard if a **confirmed** targeted defect exists. New schema must use one new forward Alembic migration. Preserve immutable task activity and supervisor review histories.
4. Maintain minimal doc changes to `README.md` and one new execution report, `docs/developer-tasks/GT-30-phase7b-execution-report.md`. Include startup instructions (API/server must be running; open/refresh app to see reminders); don't claim passive notifications when app closed.
5. Run, from `src/backend`, applicable `python -m pytest -m "not postgresql"`, full `python -m pytest` against a **dedicated PostgreSQL `_test` DB**, Ruff check/format, pip check, compileall, Alembic `upgrade head` and disposable downgrade/upgrade tests, `git diff --check` and working-tree checks. If local PostgreSQL unavailable, say exactly which were skipped/deselected and verify full PostgreSQL suite in GitHub Actions on final exact SHA.
6. Create logical Jira-keyed commits, push only feature branch, open PR to `develop`, label **STACKED ON PRs #2–#11; DO NOT MERGE**. PR body includes Jira GT-30, rules P1–P6, API contract, tests, CI head/run, upstream dependencies, limitations, Smart Life Planner audit. Report truthfully to Jira (`In Review` when implementation is submitted); never `Done` before human peer review/merge and demonstrated feature acceptance. Do not invent other developer contributions, votes, story-point approval or sprint ceremonies.
7. **Stop after Phase 7B.** Do not implement React, Flutter, Google OIDC, OTP, OCR, focus timers, analytics charts, AI, advanced notifications or Phase 8 on this run.

## 8. Agent stop conditions and required execution report

Stop and ask for a decision if a hard conflict with approved Jira/Master Plan emerges; branch is dirty in a way that would overwrite user work; the 7A fix/CI fails; a migration would destroy prior data; or implementation requires new infrastructure/credentials. Do not silently expand scope.

Report:

```text
Gate 0 progress bug: exact files, test cases, commit, PR #11 updated SHA + successful CI URL:
Phase 7B starting head after Gate 0; branch name / clean worktree:
Approved rules P1–P6 and any remaining conflicts:
Smart Life Planner reference revision + REUSE/ADAPT/REFERENCE/REJECT:
Models, migration, endpoints and sample responses:
Reminder freshness/duplicate prevention, read receipt behavior:
Role/team access tests, edge cases and cross-phase regression:
Local test counts vs PostgreSQL CI test counts (separately):
Exact final SHA and GitHub CI run, branch, PR URL and commit list:
Jira evidence/status, open upstream PR dependencies:
Limitations and manual configuration:
Phase 7B readiness; no claim of merged or live frontend:
```

## 9. Ready-to-paste Antigravity CLI startup message

```text
Read AGENTS.md, docs/Graduation_Project_Tracker_Master_Plan.md, and
`docs/developer-tasks/GradTrack_Phase7B_InApp_Reminders_Antigravity.md` completely.
Review Jira GT-30 and the current Phase 7A PR #11, report, source and tests.

I approve proposed Phase 7B rules P1–P6, local pull-based notifications,
seven-day due-soon window for tasks and milestones, and persisted read receipts only.
I authorize Gate 0's bounded Phase 7A upcoming-list bug fix on PR #11's
feature branch, followed by Phase 7B work ONLY after the updated exact-head CI passes.

Keep this as a local-first university demo. Use the chosen Flash 3.8 High mode.
Do not add cloud infrastructure, external services, background jobs, or a frontend.

Follow Git/PR rules, preserve all user work and Phases 0–7A contracts, audit
Smart Life Planner read-only, run real PostgreSQL integration and regressions,
fix confirmed in-scope bugs, then push Phase 7B as a stacked PR to develop.

Do not merge, mark Jira Done, fabricate peer approval, or start another phase.
Return the full factual report with exact GitHub heads, CI URLs, tests and blockers.
```
