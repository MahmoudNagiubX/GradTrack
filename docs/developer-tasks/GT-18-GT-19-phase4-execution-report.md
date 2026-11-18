# Phase 4 GT-18 / GT-19 Execution Report

**Date:** 2026-11-18
**Status:** Implemented; exact-head CI passed; awaiting human review.
**Task specification:** The requested repository path `docs/developer-tasks/GradTrack_Phase4_GT18_GT19_Codex.md` was absent. The complete specification was read from `C:\Users\mahmo\Downloads\GradTrack_Phase4_GT18_GT19_Codex.md`.

## Branch and upstream dependencies

Phase 4 started on `feature/GT-54-team-management` at verified head `08d9b4f979ba12ca8557e88ce26df7d1510373a9`, the head of open PR [#5](https://github.com/MahmoudNagiubX/GradTrack/pull/5). The implementation branch is `feature/GT-18-19-milestones`; PR [#6](https://github.com/MahmoudNagiubX/GradTrack/pull/6) targets `develop` and is stacked on PRs #2–#5. At the time of review, all four upstream PRs remained open and unmerged:

| PR | Task | Verified head |
|---|---|---|
| [#2](https://github.com/MahmoudNagiubX/GradTrack/pull/2) | GT-51 | `d7b215b465dd1d10719920c910b99a7ab7b82025` |
| [#3](https://github.com/MahmoudNagiubX/GradTrack/pull/3) | GT-52 | `c79cd9b172ca8d8fa2b4e115d7141de2b598525a` |
| [#4](https://github.com/MahmoudNagiubX/GradTrack/pull/4) | GT-53 | `1f1184e209aa48f0ee4e2567269ea2131a3015e0` |
| [#5](https://github.com/MahmoudNagiubX/GradTrack/pull/5) | GT-54 | `08d9b4f979ba12ca8557e88ce26df7d1510373a9` |

Do not merge PR #6 until #2 → #3 → #4 → #5 have received human review and are merged; then recheck PR #6's diff and CI. No branch was force-pushed and no shared branch was modified.

## Approved decisions

The Product Owner explicitly approved D1–D4 in the task instruction:

- **D1 — Writers:** Only a coordinator or the team's currently assigned active supervisor may create a milestone or edit its deadline. Team members can read. Students/team leaders, unassigned supervisors, and former supervisors cannot write. Authorization is checked server-side for the requested team and milestone.
- **D2 — Ownership:** Each milestone belongs directly to a team for the single-programme MVP. No `GraduationProject` model was added.
- **D3 — Deadline state:** `deadline_status` is derived from UTC time and is never persisted: `scheduled` if more than seven days remain, `due_soon` from the seven-day boundary through the exact deadline instant, and `overdue` only after the deadline. It is separate from future submission/review status.
- **D4 — Editing and history:** Authorized writers may save any valid offset-aware deadline, including a past deadline. Phase 5 must snapshot the applicable deadline for every accepted submission version so later edits do not change its historical late result. This phase adds no submission history or deadline-change actor log.

## Implementation and acceptance evidence

Added a team-owned `milestones` table and reversible Alembic migration `gt18_19_0002` with a nonblank/trimmed/length-limited name, optional description, required timezone-aware deadline, creation/update timestamps, team foreign key, and team/deadline index. Existing Phase 3 user, team, membership, and supervisor-assignment data is covered by migration preservation tests.

The API provides:

- `GET /teams/{team_id}/milestones` — lists the team's milestones in deadline then ID order, includes the UTC `due_at` and derived status, and returns `[]` for an empty list.
- `GET /teams/{team_id}/milestones/{milestone_id}` — reads only through the owning team; cross-team and mismatched IDs return `404`.
- `POST /teams/{team_id}/milestones` — coordinator or current assigned supervisor creates a team-owned milestone. Client-supplied owner/role fields are rejected.
- `PATCH /teams/{team_id}/milestones/{milestone_id}` — coordinator or current assigned supervisor changes only `due_at`. Invalid or offsetless timestamps are rejected without saving; past deadlines are accepted.

**GT-18 evidence:** Automated tests cover empty lists, shared team visibility, deadline ordering with a deterministic tie-breaker, status inclusion, details, cross-team isolation, and supervisor reassignment revoking the former supervisor's access. An empty API response is `[]`; clients should render the empty state described in `README.md`.

**GT-19 evidence:** Automated tests cover coordinator/current-supervisor create and edit permissions, student/member and unassigned/former supervisor denial, offset normalization and persistence, invalid-date no-write behavior, past deadlines, and migration constraints. An illustrative successful response includes `id`, `team_id`, `name`, `description`, UTC `due_at`, `deadline_status`, `created_at`, and `updated_at`.

## Smart Life Planner reuse audit

The local project at `C:\Users\mahmo\Desktop\Vscode\Smart Life Planner` was inspected read-only at revision `f44c4c7fe97a53d03e4df07bbbf42feaf432f9a1`. The existing timeline service and contract tests were classified **REFERENCE**: their date logic was useful to inspect, but the helper silently interprets naive datetimes as UTC. The old user-owned task model/schema were **REJECT** for this use because they do not represent team-owned milestones and do not enforce explicit offsets. No code, dependencies, environment files, logs, or data were copied or changed.

## Verification

Local checks, run from `src/backend`:

- `python -m pytest -m "not postgresql"` — **48 passed, 61 PostgreSQL-marked tests deselected**.
- `ruff check app tests migrations` — passed.
- `ruff format --check app tests migrations` — passed; 24 files already formatted.
- `python -m pip check`, `python -m compileall -q app tests migrations`, `alembic heads`, and `alembic upgrade head --sql` — passed.
- Uvicorn startup and health smoke test — `GET /health` returned exactly `200 {"status":"ok"}`.
- `git diff --check` — passed.

The full PostgreSQL suite ran in GitHub Actions on the workflow's PostgreSQL service. [CI run 44302519421](https://github.com/MahmoudNagiubX/GradTrack/actions/runs/44302519421) passed both jobs on implementation head `bf306d4eb57b1419f483162ab2d70d432ab8ec1d`: **109 tests passed**, including migration application and PostgreSQL integration tests; Ruff lint and formatting also passed. This run validated the implementation head before the report-only documentation commit; the final PR head is separately tracked on PR #6.

## Changed files and commits

- `src/backend/app/milestones.py`
- `src/backend/app/main.py`
- `src/backend/app/models.py`
- `src/backend/app/schemas.py`
- `src/backend/app/teams.py` (exposes the existing team visibility check for reuse)
- `src/backend/migrations/versions/gt18_19_0002_milestones.py`
- `src/backend/tests/test_milestone_rules.py`
- `src/backend/tests/test_milestones.py`
- `src/backend/tests/test_migrations.py`
- `README.md`

Logical implementation commits:

- `c1745953c24e87efe87dae3f535c486ba0935f55` — `feat(GT-18): add team-scoped milestone endpoints`
- `9d0adc36f9e2245187c43e32382a3bbbc36f5602` — `test(GT-18): cover milestone permissions and deadlines`
- `bf306d4eb57b1419f483162ab2d70d432ab8ec1d` — `docs(GT-19): document milestone API and deadlines`

## Remaining limitations and human actions

- Coordinator scope is temporarily global because the schema has no `Programme` entity; it is documented in the README and enforced only within the single-programme pilot model.
- Phase 5 submission records, deadline snapshots, late/on-time results, supervisor review, and deadline-change actor history are not implemented.
- Local PostgreSQL was unavailable; the full database-backed checks were verified in CI instead. No dependencies were changed.
- Existing security/architecture debt reported by the task remains: authentication rate limiting, supervisor assignment history, and the absence of a `GraduationProject` model.
- [GT-18](https://mahmoudnagiub.atlassian.net/browse/GT-18) and [GT-19](https://mahmoudnagiub.atlassian.net/browse/GT-19) remain **To Do**. Their draft estimates were not changed. No Jira update, human review, or merge is claimed.
- Human reviewers must review PRs #2–#5 in order, merge them through the approved workflow, then recheck the stacked PR #6 diff and CI before deciding whether to merge it. Phase 5 has not started.
