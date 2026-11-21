# GradTrack — Phase 7A: Timeline / Calendar Data & Progress Dashboards (Backend)

**Coding agent:** Antigravity CLI — use the user's selected **Flash 3.8 High** mode.  
**Course project:** SET312 GradTrack, local-first laptop demo; NOT cloud/production-scale.  
**Jira:** GT-29 (View Project Dates on a Calendar), GT-31 (View Team Progress), GT-37 (View Supervisor Team Progress).  
**Bounded goal:** Backend APIs that will drive React's calendar/timeline and student/supervisor dashboards. No React/Flutter screens during this backend phase.  
**Next:** Phase 7B, in-app reminders (GT-30), ONLY after Phase 7A review/report.  
**Suggested branch:** `feature/GT-29-31-37-timeline-progress`.

## 0. Grounded baseline and preflight

As checked on **20 November 2026**, `feature/GT-28-task-collaboration` is at **`f0065c12d3fd3afd271e44c2edaab2aa91a53237`**; [PR #10](https://github.com/MahmoudNagiubX/GradTrack/pull/10) is open against `develop` and not merged. The **exact-head** [CI run 44751895634](https://github.com/MahmoudNagiubX/GradTrack/actions/runs/44751895634) has two successful checks; its backend run reports **259 tests passing on PostgreSQL 16**. Previous PRs #2–#9 remain open and unmerged, and human approval/merging is **deferred, not waived**.

**Important transcript correction:** A pasted Phase 6B report contains a nonexistent SHA `f0065c1a7e44a04d5ae251ea7383749767252fc7`; the real PR #10 head is `f0065c12d3fd3afd271e44c2edaab2aa91a53237`. Update the existing report if necessary; never repeat the incorrect value. Phase 6A PR #9 was subsequently updated at `eba89a2bf383b459b6b67311f36572d16e38eb8f` with a **documentation-only** change recording its correct run. Verify Git ancestry before branching; do not assume PR #10 includes any commit made to PR #9 after #10 branched.

1. Before touching files: read root `AGENTS.md`, `docs/Graduation_Project_Tracker_Master_Plan.md` (§§2, 4, 5.2, 5.3, 5.6, delivery priorities and Agile rules), `docs/project/definition-of-done.md`, `docs/project/git-workflow.md`, Jira GT-29/GT-31/GT-37, and directly relevant source/tests/migrations. Inspect actual `git status`, remotes, latest PR heads and CI. Protect any user uncommitted work.
2. Inspect `src/backend/app/{main,auth,database,models,schemas,teams,tasks,milestones,submissions,reviews}.py`, migration heads, `src/backend/tests`, README and CI. Read the actual contracts: `GET /teams/{team_id}/tasks`, `GET /teams/{team_id}/milestones`, review inbox, team visibility, task lifecycle and late flag.
3. If predecessors are still unmerged, the PO authorizes a **stacked Phase 7A feature branch off the verified latest Phase 6B head**. If properly merged and integrated meanwhile, use verified current `develop` instead. Never merge, reset/clean away user work, force-push, rewrite shared history or push to `main`/`develop`.
4. Fix only confirmed **in-scope correctness defects**. Do not silently broaden this project to infrastructure work, user administration, deployment, Google OAuth, or full frontend implementation.

## 1. Scope and explicit technical/product rules

These rules are refinements of the approved Master Plan, not permission to add an unrelated product. The startup message must explicitly accept **R1–R6**; stop if they conflict with an existing user-approved requirement.

**R1 — Read-only computed views.** Timeline and dashboards are derived from the existing `Team`, `Task`, `Milestone`, `MilestoneSubmission`, `SubmissionVersion`, `SupervisorReview` and assignment tables. **No new timeline, calendar-event, Project, dashboard-counter or analytics tables** unless a clearly demonstrable missing capability makes them necessary and PO approves it. Do not persist counters that can go stale.

**R2 — Dates and timezones.** Accept only offset-aware query datetime boundaries, convert to UTC and return UTC timestamps. Calendar interval is **half-open `[start_at,end_at)`**; max allowed window **93 days** to cover a month view comfortably. A task with `due_at = NULL` does not appear as a dated task. Milestones always have a `due_at`. Define and test exact equality at boundaries. This is API data: React will switch week/month views client-side.

**R3 — Status definitions.** Use actual task states (`todo`,`in_progress`,`done`) and *current* milestone submission review state. Task overdue means `due_at < now` AND task status not `done`; at exact deadline it is not yet overdue. For milestones, reuse the existing Phase 4 `deadline_status` function and its **7-day due-soon threshold** rather than writing a second date classifier. Do not label a milestone "completed" unless the latest actual review is `approved`; distinguish deadline state from review state and don't turn old returned versions into current pending work.

**R4 — Visibility.** Team members view **their own teams**. Currently assigned active supervisors view only their assigned teams; a former/unassigned supervisor has no access. Coordinator remains pilot-global read-only as in existing backend; do not invent programme tables or multi-tenant infrastructure. Use existing `get_visible_team` plus a scoped query for supervisor multiple-team views. No write endpoint in Phase 7A.

**R5 — Honest progress metrics.** Show straightforward counts and exact denominators, not fictional productivity, efficiency or AI scores. Counts are computed from real rows; tasks-per-member and milestone review counts can be supported if readable and unambiguous. Empty teams return valid zeros/empty arrays, not fake sample data.

**R6 — Local and lean.** One existing FastAPI process and local PostgreSQL, reuse current modules, no event bus, Redis, cron/worker, WebSockets, cloud, push notifications, external calendar APIs, Gantt plugin backend, or paid libraries. Phase 7B will handle **in-app** reminders separately. A Gantt-like chart belongs to the React frontend and can be powered by these APIs; do not claim a working UI here.

## 2. Functional contract — GT-29 calendar/timeline data

### Outcome

Students can fetch real dated task/milestone records for a selected week/month and later open their details in the React UI. Supervisor and coordinator can see only teams they currently have permission to view.

### Suggested minimal endpoint

`GET /teams/{team_id}/calendar?start_at=...&end_at=...`

Either implement this endpoint or demonstrate that **existing authorized endpoints already deliver equivalent, efficient data** and leave no redundant new endpoint. A unified endpoint is acceptable for a clean React contract.

**If implemented**, response should be a deterministic array with a discriminated type:

- Common: `kind` (`task` / `milestone`), `id`, `team_id`, `title`, `due_at` UTC, and a safe relative/detail reference or IDs; no filesystem paths.
- Task-specific: `status`, `priority`, `assignee_id`, `milestone_id`, `parent_task_id` (when applicable).
- Milestone-specific: `deadline_status`, `review_status` when a submission exists (else null / `not_submitted` by explicit contract), and its saved deadline.
- Sort by due timestamp ASC, then stable kind and UUID tie-breaks. If a task is linked to a milestone **with different due dates**, include both as separate dated items; do not suppress or duplicate rows accidentally.
- Reject naive/malformed timestamps, `start_at >= end_at`, ranges over 93 days, unauthorized team IDs, and invalid query extras. Empty list is `[]`.
- No actual recurring-event engine, calendar sync, editing/drag-and-drop backend or dependency graph in this slice.

### Required tests

Mixed task/milestone dates, exact start inclusive/end exclusive, Cairo `+02:00` offset conversion, empty view, task no-due-date omission, one-level child task included if dated, stable ordering, record ownership, former supervisor revocation, no duplicate milestone/task rows, calendar range bound, and existing task/milestone API regressions.

## 3. Functional contract — GT-31 student/team progress summary

### Suggested endpoint

`GET /teams/{team_id}/progress`

Return an explicit typed summary derived from current rows for the visible team:

- `team_id` (and optional name if already available).
- `tasks`: `total`, `todo`, `in_progress`, `done`, `overdue`, `unassigned` **only if the current schema actually permits unassigned tasks** (current Phase 6A mandates assignees; otherwise omit `unassigned`).
- `tasks_by_assignee`: current team assignee ID and task status counts, optionally display name, with deterministic order; no bogus member activity scores.
- `milestones`: `total`, `scheduled`, `due_soon`, `overdue` for planning deadlines; **separate** `not_submitted`, `pending_review`, `returned`, `approved` for latest submission review state.
- `late_submissions`: define and document whether count uses **latest version per milestone** or **all immutable submitted versions**; for a current-progress dashboard **use latest version** to avoid double-counting old revisions; do not mutate original late flags.
- `upcoming`: small bounded list of nearest future task/milestone deadlines, deterministic sort. Include IDs/types so later React links resolve properly.
- `as_of` (server UTC) for reproducibility; tests should use a fixed/injectable clock where possible.

No storing of summary totals in the database. If counts can be composed from existing authorized endpoints with no meaningful duplication/complexity, document that and keep the backend lean. However, if a single summary endpoint simplifies one-request dashboard data and avoids repeated client fetches, prefer that minimal endpoint. Do not add a repository/service layer merely for aesthetic architecture.

### Required tests

Empty team; mixed task lifecycle and deadlines; exact boundary on overdue; assigned and reassigned tasks; milestone deadline status vs review status; first submission, returned version, resubmitted version, approval; count latest version not all versions; cross-team and former supervisor denies; coordinator existing pilot-only read access. No invented user efficiency score.

## 4. Functional contract — GT-37 supervisor assigned-team progress

### Suggested endpoint

`GET /supervisor/teams/progress`

- Only authenticated **active supervisor** can use this endpoint. Coordinator is not automatically a supervisor for this route.
- Query teams currently assigned to the calling supervisor from the actual `SupervisorAssignment` rows, then compute the **same** summary semantics as team progress, with team IDs/names, overdue tasks/milestones, pending reviews and next deadline.
- Do **not** query unscoped all-team rows and filter them after serialization; scope the data in SQL to assigned teams.
- Formerly assigned teams disappear as soon as reassigned. No leak through counts, error responses, or list entries.
- Empty assignment set => `[]`; stable ordering; no novel supervisor approval route.
- Optional coordinator summary is not required by GT-37 and belongs to a later, explicitly scoped increment unless simple reuse suffices without new endpoints.

### Required tests

Supervisor with 0/1/multiple teams, teams assigned to another supervisor, reassignment, inactive supervisor, students/coordinators forbidden, accurate pending counts with returned and approved versions, stable ordering. Use real PostgreSQL.

## 5. Cross-phase integrity and the discovered Phase 6B downgrade edge

**Known audit concern to confirm, not hide:** `gt28_0006_task_collaboration.py` downgrade drops task collaboration tables and restores an older `ck_task_activities_event_type` constraint **excluding** `comment_added` and `attachment_uploaded`, but Phase 6B keeps those append-only task activity rows. Therefore, when such rows exist, the downgrade can fail. The current migration tests appear to clean sample events before downgrading; that does not prove a real populated downgrade works.

Before Phase 7A schema work, reproduce this in a disposable PostgreSQL test DB. Do not disable immutable audit triggers/delete actual data just to fake a green migration test. A safe, bounded approach for this university demo is to **fail explicitly with a helpful error on downgrade if Phase 6B activity exists** (since preserving that audit and removing its schema is inherently conflicting), or propose a genuine reversible schema plan for PO approval. If the fix is more than a small in-scope correction, report it separately and continue Phase 7A read-only API work; **don't overengineer migration frameworks** or change production-like data without permission.

Also correct **factual SHA/CI** documentation errors in the existing Phase 6B report, using the real GitHub PR #10 head and exact-head run; do not create duplicate reports for this.

### Mandatory cross-phase demonstration

Register/login student and supervisor identities via existing tested setup → team creation/assignment → milestone + deadline → task assignment/status/comment/attachment → student file/link milestone submission → supervisor return/revise/approve → calendar list and team progress reflect actual latest state → supervisor assigned-team progress reflects only authorized teams → reassignment removes former supervisor access. Build tests with synthetic data and real PostgreSQL, reusing existing fixtures.

## 6. Smart Life Planner reuse audit — read only, every phase

At `C:\Users\mahmo\Desktop\Vscode\Smart Life Planner` (previously observed revision `f44c4c7fe97a53d03e4df07bbbf42feaf432f9a1`), inspect only relevant timeline/calendar and dashboard services or tests. Capture the actual revision, candidates classified **REUSE / ADAPT / REFERENCE / REJECT**, and reasons (old async SQLAlchemy and personal-task assumptions do not automatically transfer). Reuse a small compatible function if it genuinely reduces effort; do not copy old auth/email/secrets, migrations, entire personal-task framework or UI. Keep a few lines of audit in the Phase 7A report.

## 7. Work plan and quality gates

1. Confirm R1–R6, stack branch, clean tree, baseline CI and current backend contracts. If critical decision is unapproved, stop before affected code writes.
2. Inspect Smart Life Planner read-only; preserve GradTrack's tested sync FastAPI/SQLAlchemy architecture.
3. Implement GT-29 timeline/calendar **data** with tests; don't build Gantt UI or project-stage templates here.
4. Implement GT-31 team progress summary with correct current-state semantics; reuse milestone deadline classifier and version history logic.
5. Implement GT-37 supervisor assigned-team rollup; one shared internal summarizer is okay; avoid duplicated counting logic across routes.
6. Inspect/update OpenAPI, README and a single concise execution report; keep changes within relevant backend modules and tests. Add new dependency/schema migration **only when actually necessary**. If no migration is needed, report that plainly.
7. Run targeted tests, full `pytest` against a real PostgreSQL 16 database in CI, Ruff lint/format, `pip check`, `compileall`, `git diff --check`, CI job logs and PR checks. Fix confirmed regressions and auth leaks; do not disable tests to get green.
8. Push only the new phase branch, open a **STACKED PR to `develop`**, verify its actual final-head SHA/CI. Do not merge PRs #2–#10 or the new one; no Jira Done, fabricated sprint approvals or Phase 7B work.

### Suggested commands (from `src/backend`; adapt to actual environment)

```powershell
python -m pytest -m "not postgresql"
python -m pytest
ruff check app tests migrations
ruff format --check app tests migrations
python -m pip check
python -m compileall -q app migrations tests
```

For local PostgreSQL absence, clearly report that local DB tests did **not** run; GitHub Actions with PostgreSQL 16 is the integration evidence. Use disposable `_test` database; never destructive test a live personal DB. Inspect actual CI runs on the exact final SHA; distinguish old-head CI from final-head results.

## 8. Acceptance and Agile/Jira status

- GT-29 calendar data supports the later **visible week/month UI**; **backend data alone does not satisfy the story's UI acceptance criterion**. Do not mark GT-29 Done or claim the user can click a finished calendar.
- GT-31 progress endpoint similarly supports the future dashboard UI; backend-only work is **partial story fulfillment** until visual dashboard integration.
- GT-37 supervisor progress endpoint is backend-only; actual supervisor dashboard remains pending React frontend.
- Update Jira with truthful API implementation evidence, tests, PR and relevant status such as `In Progress` or `In Review` as warranted; do not misrepresent UI completion or estimates. Do not invent team reviews or actual Story Point votes.
- Continue the previously approved staged-development exception: feature branches may stack but human review and merging remain deferred, not waived.

## 9. Final response required from Antigravity

```text
Phase 7A result: Complete / Partial / Blocked (backend scope only)
Model/mode observed in Antigravity:
Source branch, SHA, PR #2–#10 status, clean/dirty tree:
Approved R1–R6 and conflicts:
Smart Life Planner inspected revision; REUSE/ADAPT/REFERENCE/REJECT:
Actual API routes and example responses:
Counts/status definitions and as_of UTC:
Roles/team isolation and wrong-team tests:
Milestone/task/deadline/review integration results:
Phase 6B downgrade edge reproduced? Safe handling or documented blocker:
Migrations needed or not (and why):
Exact test commands, pass/fail/deselected/skip counts:
GitHub Actions exact final-head run ID, SHA and link:
Code files changed, commits, branch and stacked PR URL:
Jira evidence/status (backend-only, UI pending):
Known limitations and user configuration required:
Next recommended work (7B only after review):
```

### Ready-to-paste Antigravity CLI startup prompt

```text
Read AGENTS.md and docs/Graduation_Project_Tracker_Master_Plan.md,
then read docs/developer-tasks/GradTrack_Phase7A_Timeline_Dashboards_Antigravity.md
completely. Consult Jira GT-29, GT-31 and GT-37 and verify current source.

I approve Phase 7A rules R1–R6 and authorize backend implementation ONLY.
This is a polished LOCAL university/portfolio demo, not a cloud SaaS.
Continue stacked development from the latest verified Phase 6B PR #10 head
if predecessors remain unmerged. Never merge a PR or change shared branches.

Implement accurate team calendar/timeline data and team/supervisor progress
summaries, respecting team permissions, UTC date boundaries, actual task
statuses, real latest-version review states and existing 7-day milestone
status logic. Avoid new persistence/infrastructure unless demonstrably needed.

Inspect Smart Life Planner's relevant timeline code read-only, reuse GradTrack
helpers, test the full previous backend integration, and identify/handle the
known Phase 6B populated-downgrade edge safely without deleting immutable
history merely to force a green test. Correct verified SHA/report typos.

Run full regression and PostgreSQL 16 CI at the EXACT final PR head, Ruff,
API/security checks and diff review. Fix actual in-scope bugs. Make focused
commits, push a feature branch and open a STACKED PR to develop. Update Jira
evidence truthfully, noting the Calendar/Dashboard UI itself remains undone.

Do not merge, mark issues Done, start React/Flutter, implement Phase 7B
notifications, or add cloud services. Return the structured implementation
report requested by the MD and stop.
```
