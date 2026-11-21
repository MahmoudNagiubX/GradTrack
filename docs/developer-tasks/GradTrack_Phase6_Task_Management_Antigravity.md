# GradTrack — Phase 6: Team Task Management

**Implementation contract for Antigravity CLI (user-selected Flash 3.8 High mode)**  
**Date prepared:** 20 November 2026  
**Project:** GradTrack — local-first university course and portfolio demo  
**Repo:** `MahmoudNagiubX/GradTrack`  
**Jira:** GT-26 — Create and Assign a Team Task; GT-27 — Update Task Progress; GT-28 — Add Comments and Files to a Task  
**Output:** Backend FastAPI + PostgreSQL only. One shared backend for later React web and Flutter mobile clients.  
**Implementation order:** **Phase 6A (GT-26 + GT-27) → report/review gate → Phase 6B (GT-28)**. **Do 6A only on the first invocation.**

> **Required initial reading:** Root `AGENTS.md`, `docs/Graduation_Project_Tracker_Master_Plan.md` (especially §2, §4, §5.2, §5.3, §5.5, priorities, Agile process and backlog), `docs/project/git-workflow.md`, `docs/project/definition-of-done.md`, Jira GT-26–GT-28, this task and relevant existing backend code/tests. The Master Plan is the scope authority; this document refines one phase without deleting future features.

## 1. Verified starting state — refresh before editing

As of the live repository check on 20 November 2026:

- **Latest completed feature branch:** `feature/GT-22-25-supervisor-reviews` (Phase 5B), **SHA `89d824727ef38b228c0c0bc5575f1212edaca764`**; [PR #8](https://github.com/MahmoudNagiubX/GradTrack/pull/8) targets `develop`, remains open and unmerged.
- **Exact-head GitHub Actions:** [run 44333136961](https://github.com/MahmoudNagiubX/GradTrack/actions/runs/44333136961): both backend tests/lint and repository-check succeeded. The execution report documents **219 PostgreSQL-backed tests passed** (do not treat this number as the Phase 6 result).
- Earlier **PRs #2 → #3 → #4 → #5 → #6 → #7 → #8** are also open and unmerged, awaiting genuine human reviews; reviewer approval is **deferred, not waived**. Never claim `develop` contains their backend code.
- **Current backend:** FastAPI, synchronous SQLAlchemy 2, PostgreSQL 16 in CI, Alembic through `gt22_25_0004`, Argon2id/PyJWT, student/team/leader/coordinator/supervisor permission patterns, team-owned milestones, private file submissions, immutable version history, assigned-supervisor review.
- Existing modules: `src/backend/app/{main,auth,teams,models,schemas,milestones,submissions,submission_storage,reviews,supervisor_assignments,database,config}.py`. No existing `tasks.py` module or task model was found at the checked Phase 5B head.
- **Jira GT-26, GT-27, GT-28:** `To Do`. Their descriptions: GT-26 create/assign task with title, owner and status; GT-27 assigned member changes `To Do`/`In Progress`/`Done` with actor recorded; GT-28 team comments and supported file/image attachments, with author and date.
- Jira currently labels these stories `priority-2`, while Master Plan §6 places collaborative task management in **Priority 1**. Do not silently reassign story points, alter labels or claim sprint agreement. Record the discrepancy for PO/backlog review.

### Git/branch gate

1. Verify actual branch, working tree (`git status --short`), remote and current head. Preserve user changes; no `reset --hard`, destructive clean, hidden stash, force-push or rewrite of published history.
2. Fetch remote and recheck live PRs, lineage, SHA and exact-head CI. If all earlier PRs have been **human-reviewed, merged and verified**, branch from the updated tested `develop`.
3. Otherwise, the Product Owner's instruction to continue stacked development allows **Phase 6A on a new branch based on the latest verified Phase 5B head**. Suggested: `feature/GT-26-27-task-core`. **Do not modify Phase 5B's branch.**
4. When Phase 6A tests and exact-head CI pass, create PR to `develop`, clearly marked **STACKED — NOT FOR MERGE** until the predecessors pass human review and merge. The PR diff against `develop` will include predecessors; describe which commits/files actually belong to Phase 6A and recheck reduced diffs after upstream merges.
5. **Stop after the Phase 6A report.** Do not implement 6B or Phase 7 without a new instruction, even if the code can be written quickly.

## 2. Scope and simplicity rules

This is a **single-laptop university demo**: local PostgreSQL, local file storage, local FastAPI. No cloud, Docker/Kubernetes, Redis, background workers, microservices, queues, enterprise audit platform, payments or production observability. Existing useful security checks are still mandatory: team isolation, correct permissions, valid file data and no secrets.

Use existing auth dependencies, `get_visible_team`, team membership checks, SQLAlchemy session fixtures, migrations, storage functions and tests. A cohesive `app/tasks.py` and task models are reasonable. Do **not** scatter trivial helpers into `utils.py`, `services/`, `repositories/`, `task_helpers.py`, etc. solely for cosmetic architecture. `app/task_collaboration.py` is optional in 6B if and only if comments/upload routes would make `tasks.py` unwieldy.

Frontend UI (Kanban display, visual list, drag-and-drop, mobile screens) is **not** to be implemented now. Backend response/filter APIs should let React and Flutter build those views later. No WebSocket or real-time push is required: data become visible after the next API fetch.

## 3. Proposed decisions — Product Owner must explicitly approve in startup prompt

The Master Plan and Jira define intent, but not every field/permission. These are intentionally **simple proposed defaults**, not hidden authority to alter the product. A copied startup prompt below includes explicit approval; if the user removes that approval or a higher-priority project instruction conflicts, inspect first and ask before affected writes.

**D1 — Team-level task permissions**
- **Current active team leader** creates tasks, assigns/reassigns them and changes task metadata, due date, priority, milestone association and checklist/subtasks.
- A **current active team member assigned to the task**, including a leader when assigned, can update their own task status. The team leader can also update the status of any task in their team for coordination, with an attributable history entry.
- **Any current team student member** may view all their team's tasks; supervisors assigned to that team and coordinators have **read-only** access using existing pilot scope. Nonmembers and former supervisors cannot see team tasks. No public/guest access.
- Do not assume a student is a leader because of a system role; verify `TeamMembership.role == 'leader'` for the **specific team**.

**D2 — Task lifecycle:** Exactly three base status values: `todo`, `in_progress`, `done` (mapped to Jira's To Do / In Progress / Done). New tasks start `todo`. Done and reopening are permitted with accurate actor/time history; moving out of `done` clears current completion metadata while preserving historical events. `blocked` is **not** a fourth workflow status; a short optional blocker note/flag can be added only if minimal and needed for the Master Plan's blocker visibility.

**D3 — Ownership & required fields:** Every task belongs to one `Team`, has a trimmed nonblank title (e.g. max 200 chars), a creator, one current active **student member** assignee, status and timestamps. Optional description, `due_at` (timezone-aware UTC), priority (`low`,`medium`,`high`), estimated minutes (positive, bounded), and nullable link to an **existing milestone owned by the same team**. No separate Project entity. Allow due dates in the past; don't invent a rule that prevents tracking overdue work.

**D4 — Subtasks and checklists:** Support a simple one-level `parent_task_id` child task in the **same team**, no nested grandchildren, no cycles; child tasks follow the same assignment and status rules. Support simple checklist items (text, done flag, creator/completer timestamps) for a task. No automatic parent completion from subtask statuses and no checklist-to-task automatic state transition. Keep real progress observable rather than calculating fictional productivity scores.

**D5 — Task activity:** Record actual creator, current assignee, last editor, actual completer and server timestamps. Store compact append-only task activity events for creation, assignment/reassignment, status changes/reopen and meaningful task edits/checklist changes; no fabricated backdated history. Keep API activity ordered, scoped to the task and attributable to an actor. Avoid comprehensive event-sourcing or tracking every insignificant read.

**D6 — Filtering/board support:** Return team task list, scoped task detail and history; allow practical optional filters (`status`, `assignee_id`, `priority`, `milestone_id`, `due_before`, `due_after`, `parent_task_id`) and deterministic ordering. Empty lists return `[]`. A Kanban board is a React/Flutter presentation of the same status-groupable task records; don't create a separate board database or duplicate task collection.

**D7 — Phase 6B collaboration:** Members of a team can post comments and attach validated files/images to team tasks; assigned supervisor and coordinator can read comments/attachments under the existing team read scope but cannot write them. Comments are append-only in the MVP with author and UTC timestamp, no edit/delete endpoint. Files use the existing **private local storage** policy (20 MiB and supported formats), opaque key, authorized download and safe failure handling; no public static uploads and no extra cloud service. This decision only authorizes 6B **after the 6A report gate**, not on first run.

These decisions must be explicitly acknowledged in the Phase 6A startup instruction. If a decision conflicts with Jira/Master Plan or an actual user-approved behavior, stop on that item and report the conflict.

## 4. Phase 6A — GT-26 & GT-27: core tasks, assignments and progress (DO NOW)

### GT-26 — Create and assign a team task

- Active leader creates a task within `team_id`; creator auto-recorded, no forged user/role fields.
- Assignee must be an **existing active student member of that same team**. Inactive users, other-team students, supervisors, coordinators or absent members must be rejected. Leader may assign to self.
- The task includes `title`, `status`, `assignee`, optional `description`, `priority`, `due_at`, `estimated_minutes`, `milestone_id`, `parent_task_id`. Normalize/validate strict fields and return stable typed JSON. No unapproved file attachment in 6A.
- The task appears in the team list, filters and detail; assignee can read it; all current team members see the same current task data.
- Leader can update task metadata/assignment within the same team. Reject cross-team milestone or parent/assignee references; do not silently move a task to another team.
- Create/manage checklist items and one-level subtasks as described in D4 (only if approval present). Users see task progress based on real stored statuses/checklist completion, not made-up aggregate scores.

### GT-27 — Update progress and record actual actor

- Assigned active student can move task `todo ↔ in_progress ↔ done`; leader can adjust status on any team task. Every **actual change** records actor and UTC timestamp; avoid duplicate events for idempotent no-op updates.
- Marking `done` records `completed_by` and `completed_at`. Reopening preserves historical completion event(s) and clears only current completion metadata, not past evidence.
- Students cannot alter another member's task progress unless they are a leader. Supervisor/coordinator read-only.
- Member removal/role changes must be rechecked against current membership at mutation time; current assignee can become ineligible if removed, so prevent further writes and report how reassignment is handled.
- Server-side validation: unknown statuses, malformed due timestamps, negative estimate, unknown IDs, team mismatch, inactive user, forged actor/status fields must fail predictably without partial mutation.

### Minimal suggested HTTP contract — follow existing API naming/conventions

| Method | Path | Authorized use |
|---|---|---|
| `GET` | `/teams/{team_id}/tasks` | Current team viewers; supports listed filters |
| `GET` | `/teams/{team_id}/tasks/{task_id}` | Current team viewers; detail + optional checklist/subtasks |
| `POST` | `/teams/{team_id}/tasks` | Active team leader creates/assigns |
| `PATCH` | `/teams/{team_id}/tasks/{task_id}` | Active team leader edits task metadata, assignment |
| `PATCH` | `/teams/{team_id}/tasks/{task_id}/status` | Assigned member or same-team leader changes status |
| `GET` | `/teams/{team_id}/tasks/{task_id}/activity` | Current team viewers, chronological history |
| `POST` | `/teams/{team_id}/tasks/{task_id}/checklist` | Active team leader adds checklist item |
| `PATCH` | `/teams/{team_id}/tasks/{task_id}/checklist/{item_id}` | Assignee or same-team leader changes done flag; leader may edit text |

Use `POST /teams/{team_id}/tasks` with optional `parent_task_id` for one-level subtasks; do not create duplicate `/subtasks` CRUD solely for convenience. No unscoped global task enumeration. Preserve standard error bodies and non-enumerating cross-team `404` patterns from existing routes.

### Storage design: small, cohesive, reversible

Suggested models (adapt to existing conventions):

- `Task` with UUID key, `team_id` FK, `created_by`, `assignee_id`, `updated_by`, `completed_by` FK(s), valid status/priority checks, title/description, optional offset-aware `due_at`, `estimated_minutes`, optional same-team `milestone_id`, optional one-level same-team `parent_task_id`, and server UTC `created_at/updated_at/completed_at` as applicable.
- `TaskChecklistItem` with UUID key, task FK, text, done flag, created/updated/completed actor and timestamps (only fields actually needed).
- `TaskActivity` with UUID key, task FK, actor FK, timestamp and compact event type plus small safe before/after metadata needed to answer who assigned/changed/completed what. Use simple typed columns or limited fields; avoid generic complex JSON event frameworks.

Add **one new Alembic migration after `gt22_25_0004`**, never modify previously applied revision files. Enforce realistic FKs/indexes, including team/status/assignee for filters. Validate **same-team** milestone/parent references and membership at the API layer (and DB constraint where simple); integration-test them. Make migration reversible in disposable test DB. Preserve older users, teams, milestones, submissions, review records and stored private files.

### Required GT-26/27 tests (real PostgreSQL, not only mocks)

1. Fresh migrated DB and upgrade from Phase 5B with existing team/milestone/submission/review rows preserved; safe isolated downgrade/upgrade.
2. Leader creates a task and is recorded as creator; correct assignee/milestone/team; list/detail both reflect it.
3. Bad/missing title, inactive user, wrong-role assignee, other-team assignee and invalid/mismatched milestone rejected.
4. Member cannot create or reassign; supervisor and coordinator cannot write; current leader can edit.
5. Assigned member changes progress; unassigned team member cannot change it; other-team users and former supervisors cannot read/write.
6. Completion actor/time recorded; reopening clears current completion fields while history remains intact; no-op status does not invent activity.
7. One-level subtask and checklist lifecycle; same-team restriction, no self-parent or 2+ levels; correct scoped visibility.
8. UTC offsets / Cairo `+02:00` conversion, malformed/naive dates, due date in the past, ordering and filtering, empty results.
9. Concurrent or competing update scenarios do not corrupt current task state or create misleading actor/history records; use row locking where needed.
10. Cross-phase end-to-end: register/login student → team created → leader adds member → coordinator assigns supervisor → supervisor creates milestone → leader creates task linked to milestone assigned to member → assignee marks in progress/done → leader and supervisor can view legitimate activity → unrelated student/supervisor denied. Ensure existing milestone submission/review paths still work.
11. Re-run entire Phase 0–5B regression suite, including private upload/download and immutable supervisor review history.

**Test commands** from `src/backend` (adapt to actual `pyproject.toml`):

```powershell
python -m pytest -m "not postgresql"
python -m pytest
ruff check app tests migrations
ruff format --check app tests migrations
python -m pip check
python -m compileall -q app migrations tests
```

Also `git diff --check`, API/OpenAPI inspection, Alembic head and actual migration `upgrade head`; test downgrade only on a **disposable** DB. If local PostgreSQL is unavailable, report local deselections honestly and require **exact pushed-head GitHub Actions PostgreSQL 16 success**; don't substitute SQLite and pretend it proves equivalence. Don't adjust/disable tests to pass CI.

### Phase 6A completion gate

Once GT-26 and GT-27 scope is implemented and verified:

1. Self-review changed files and full diff, check cross-team permissions, statuses, timestamps, API response stability and regression impact. Fix confirmed *in-scope* bugs.
2. Make logical Jira-keyed commits and push `feature/GT-26-27-task-core` (or clearly named equivalent), create **stacked PR against `develop`** only if possible and label dependency on #2–#8; never merge it.
3. Update **one concise Phase 6A execution report** in `docs/developer-tasks/` plus appropriate README/API examples and Jira evidence. Move GT-26/27 at most to `In Review` when supported; do not mark `Done` before human review, merge, CI and required PO/Sprint acceptance.
4. Return branch/base SHA, exact CI URL and SHA, actual test results, model/migration/API list, audit findings, Jira status, known issues and **stop**. User/ChatGPT reviews the Phase 6A report before authorizing 6B.

## 5. Phase 6B — GT-28: comments and task attachments (LATER, NOT FIRST RUN)

Only implement when explicitly asked **after** Phase 6A checks and review. Re-read live 6A API/model/test results and create a new branch based on its verified head if still stacked. Suggested `feature/GT-28-task-collaboration`.

### Functional behaviors

- Current active student members of the owning team can add a comment (trimmed, nonempty, bounded text) to a task; all authorized team viewers read ordered comments with author and server UTC timestamp. An inactive/foreign user cannot comment or read. Supervisor assigned to the team/coordinator is read-only.
- Current members may attach a supported document/image/file to a task; metadata include uploader, task, size, name, UTC time, media type and opaque storage key. Reuse the **existing private local file storage** policy and validation, no public file path, no Google Drive or cloud and no new upload framework.
- Download via authenticated, **task-scoped** route that revalidates current team visibility. Do not leak storage path, key, or files from other teams. Adopt safe attachment response headers and streaming already used by milestone submissions.
- Comments and attachment additions produce attributable task activity events and do not interfere with formal milestone submissions/version history. No comment editing/deletion, automatic notifications, full-text search or virus-scanning infrastructure in this local-demo phase.
- Optional relevant HTTPS reference URL on a task may reuse `validate_submission_url` only if the actual Master Plan/Jira/API need justifies it. Do not fetch arbitrary URLs server-side.

### Suggested routes

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/teams/{team_id}/tasks/{task_id}/comments` | Team-scoped list |
| `POST` | `/teams/{team_id}/tasks/{task_id}/comments` | Member comment |
| `GET` | `/teams/{team_id}/tasks/{task_id}/attachments` | Team-scoped attachment list |
| `POST` | `/teams/{team_id}/tasks/{task_id}/attachments` | Validated single file/image upload |
| `GET` | `/teams/{team_id}/tasks/{task_id}/attachments/{attachment_id}/download` | Authorized private streaming download |

### Tests and acceptance

- Safe comment creation, author/time, empty/malformed/too-long content and access boundaries.
- PDF and image attachment upload, correct metadata, authorized download, wrong-team/removed-member/old supervisor denial.
- Oversize, invalid extension/MIME/content, path traversal, unavailable root and DB-write failure after file promotion all leave consistent DB and filesystem state; report known crash-orphan limitation.
- Comments/attachments appear in activity with real actor/time and in correct task, not across teams.
- Regression against complete prior API/test suite, exact-head PostgreSQL CI, one concise report, stacked PR, Jira `In Review` only when appropriate, **no merge or Phase 7 work**.

### Extras from Master Plan to handle honestly

- Tags/categories and richer dependency links are approved *future product capabilities* but not independently scoped as Jira GT-26–GT-28 acceptance criteria. Build them only where the PO explicitly approves a small defined behavior; don't invent complex tagging or dependency graphs. Timeline/dependency UI belongs in Phase 7 planning, not a surprise feature in 6A.
- @mentions and reminder notifications are planned; Phase 6B can store plain comment text but must **not claim** working notifications or add an event queue.

## 6. Mandatory Smart Life Planner reuse check — each subphase

Read-only local reference: `C:\Users\mahmo\Desktop\Vscode\Smart Life Planner`, previously observed commit `f44c4c7fe97a53d03e4df07bbbf42feaf432f9a1`; verify actual path/HEAD, do not modify it.

For **6A**, inspect relevant old `backend/app/models/task.py` (including `TaskCompletionEvent`), task schemas/routes/repositories and tests. For **6B**, inspect old task notes/attachments/feedback only where useful. Classify candidates as **REUSE / ADAPT / REFERENCE / REJECT** with reason: GradTrack's sync SQLAlchemy, team role scoping, existing tested API and migration compatibility. Prefer reusing concepts/tests over copying incompatible code; old security/async DB and exposed attachment paths were rejected in earlier audits. Do not copy `.env`, credentials, real data, unrelated dependencies or entire old modules. Capture concise findings in each phase report, not another sprawling audit file.

## 7. Agile and documentation rules

- Respect the Master Plan and actual sprint assignments. Jira GT-26/GT-27/GT-28 currently show **draft story-point estimates** (3/2/3); don't change to agreed estimates without actual developer confirmation.
- Each implementation should link AC, actual code/tests/PR/CI and real dates; do not invent stand-ups, Planning Poker votes, sprint reviews, historic commits or teammate approvals.
- Keep README/run instructions accurate for a clean Windows laptop setup and optional LAN-based later Flutter demo; add no cloud/deployment work.
- Minimal purposeful files only: update existing code/schema/migrations/tests as appropriate and **one** focused execution report per executed subphase. Do not create unnecessary design docs, duplicate framework layers or premature frontend files.
- A PR's green CI proves executed checks, **not** human approval or integration into `develop`.

## 8. Required Antigravity CLI implementation report

```text
Subphase (6A or 6B) and Jira keys:
Agent/model selected by user (report observed configuration; don't invent capabilities):
Actual starting branch, SHA, upstream PR state, working-tree status:
Approved D1–D7 or unresolved decision:
Smart Life Planner inspected path/commit; reused/adapted/referenced/rejected:
Models, Alembic revision, routes and changed files:
Roles and cross-team isolation verified:
Acceptance criteria, edge cases and full cross-phase integration tested:
Local commands/tests (including skips/deselected):
PostgreSQL GitHub Actions run URL, exact head SHA, pass/fail counts:
Regression bugs found/fixed:
Commits, branch, PR and its stacked dependencies:
README and Jira evidence/true statuses:
Known limitations/manual steps:
Recommended next subphase; STOP without starting it:
```

## 9. Ready-to-paste Antigravity startup prompt (FIRST RUN: PHASE 6A ONLY)

```text
You are the coding agent for GradTrack. Use my currently selected Flash 3.8 High
mode in Antigravity CLI; do not silently change the model or profile.

Read repository-root AGENTS.md, the full Master Plan, Jira GT-26/GT-27,
and docs/developer-tasks/GradTrack_Phase6_Task_Management_Antigravity.md.

I explicitly approve decisions D1 through D7 in that task file as the
implementation contract for the local-first university demo, subject to any
higher-priority approved Master Plan/Jira conflicts being reported rather
than guessed. I authorize only Phase 6A (GT-26 + GT-27) execution now.

If upstream PRs #2 through #8 are still open and unmerged, I authorize
stacked development on a NEW feature branch from the latest verified
Phase 5B head, after confirming exact-head CI. This is NOT permission to
merge, rebase published history, push directly to develop/main or self-approve.

Implement team-owned tasks, leader assignment, assignee/leader status updates,
subtasks/checklists, due dates/priority/estimates/milestone links, simple
filters and accurate actor/completion history. Reuse existing FastAPI,
PostgreSQL, auth, team scoping and tests. Review Smart Life Planner code
read-only and reuse only truly compatible parts. No cloud, frontend, extra
infrastructure or unnecessary files.

Run tests, including full regression and real PostgreSQL CI on the EXACT
pushed head. Fix genuine in-scope bugs. Make logical commits, push a Phase 6A
feature branch, and create a clearly stacked PR targeting develop. Update
README and truthful Jira evidence, but mark nothing Done and merge nothing.

STOP after Phase 6A. Deliver the precise implementation/test/CI/PR report
specified in section 8. Do not implement GT-28 or Phase 7 yet.
```

**Do not assume CLI flags or commands.** Paste this prompt into the actual configured Antigravity CLI session opened in the GradTrack repository. A model label selected in the UI/CLI is a user choice, not evidence of what tools or permissions the agent can use; the agent must report any unavailable capability rather than pretending to have used it.
