# GT-22 to GT-25 Phase 5B Execution Report

**Date:** 2026-11-18

**Result:** Implemented and verified on GitHub Actions; PR is open for human review. No PR was merged.

## Scope and decisions

Implemented only GT-22, GT-23, GT-24, and GT-25. The Product Owner approved D1-D5 in this session: latest-pending review, required return feedback, approval finality, current active supervisor authorization, immutable version/review history, and temporary global read-only coordinator access for the single-programme pilot. Stacked development from the verified GT-20/21 head was authorized.

Initial local state was a clean `feature/GT-20-21-submissions` checkout at `801284df781b0b32c2b28e040bb42b06a47299ea`. PR #7 was open at that exact head and its PostgreSQL CI passed. PRs #2-#7 remained open and unmerged at the final check. The Phase 5B branch was based on the verified PR #7 head.

## Implementation

- Added `SupervisorReview`, with one review per submission version, reviewer attribution, decision/feedback constraints, and a PostgreSQL trigger rejecting updates and deletes. Added forward migration `gt22_25_0004` after `gt20_21_0003`; it preserves existing Phase 5A rows and downgrades only the new review objects.
- Added `GET /supervisor/submissions/pending`, review `POST` and team-scoped history `GET`, and link/file revision `POST` routes.
- Only the current active supervisor assigned to the team can approve or return the latest pending version. A return requires 1-2000 trimmed characters. Approval feedback is optional. Coordinators and students cannot write reviews; authorized coordinator reads remain pilot-global under the existing single-programme schema.
- Revisions are accepted only after a return. They append a new immutable version, set the thread back to pending, snapshot the current UTC deadline, and compute lateness without changing earlier version data. Existing HTTPS validation, private file staging, 20 MiB upload bound, and authorized download paths are reused.
- Version history derives each version's status from its own review, with an unreviewed version shown as `pending_review`.
- Review and revision operations lock the submission parent. Revisions lock milestone then parent and re-check the active account and team membership. Review decisions re-read the active account and lock/re-check the current supervisor assignment after locking the parent.
- Self-review found and fixed a cross-team review-read path mismatch; a PostgreSQL test now ensures an authorized team ID cannot be combined with another team's milestone/version.
- No dependencies were added. No Phase 6 work was started.

## Smart Life Planner reuse audit

**Local path:** `C:\Users\mahmo\Desktop\Vscode\Smart Life Planner`

**Inspected revision:** `f44c4c7fe97a53d03e4df07bbbf42feaf432f9a1`

The old project was inspected read-only and not modified. No Smart Life Planner code was copied or adapted.

| Candidate | Classification | Compatibility and security assessment | Expected integration effort |
|---|---|---|---|
| `backend/app/core/security.py`, `backend/app/api/v1/auth.py`, `backend/app/core/dependencies.py` | REJECT | The old auth choices and role/dependency assumptions do not match GradTrack's Argon2id, PyJWT, and synchronous SQLAlchemy implementation. Replacing the current tested auth stack would add risk and work. | None for this phase; replacement would require a separate reviewed auth migration. |
| `backend/app/core/database.py`, `backend/app/models/user.py`, `backend/app/repositories/user_repository.py`, `backend/app/schemas/user.py` | REJECT | Async DB and older account schema conflict with GradTrack's synchronous access and existing migrations. No compatible review behavior is gained. | None; adopting would require substantial schema and persistence redesign. |
| `backend/app/services/email_service.py` | REJECT | The development fallback can expose verification material through logs or responses. No email, OTP, or verification flow is in GT-22 to GT-25. | None; future email work needs a separate security review. |
| `backend/app/models/feedback.py`, `backend/app/schemas/feedback.py`, `backend/app/repositories/feedback_repository.py`, `backend/app/api/v1/feedback.py` | REFERENCE | Generic personal feedback is not team- and submission-version-scoped and uses the old async persistence pattern. No code was reused. | Low conceptual effort, but a new version-scoped model/API remains necessary. |
| `backend/app/models/note.py` (`NoteAttachment`) and related schema/repository | REJECT | Note attachments expose local-path/URL concepts without the required team authorization and private download boundary. | None; secure attachment handling already exists in GradTrack. |
| `backend/app/models/task.py` (`TaskCompletionEvent`) and its contract tests | REFERENCE | The audit-event idea is relevant to future history work, but task completion is not a supervisor decision and its ownership rules do not transfer. | Low for a future design reference; no adaptation was needed for review history. |
| `backend/app/services/project_timeline_service.py` and tests | REFERENCE | Potential future timeline reference only; unrelated to version review and resubmission. | Moderate future adaptation; no work in GT-22 to GT-25. |

GradTrack's existing `app.submission_storage.stage_upload`, URL validation, and team-scoped submission/download flow were reused directly. Google Sign-In, OTP/email, password reset, and timeline ideas remain future candidates, not implemented features.

## Files changed

- `README.md`
- `src/backend/app/main.py`
- `src/backend/app/models.py`
- `src/backend/app/reviews.py` (new)
- `src/backend/app/schemas.py`
- `src/backend/app/submissions.py`
- `src/backend/migrations/versions/gt22_25_0004_supervisor_reviews.py` (new)
- `src/backend/tests/test_migrations.py`
- `src/backend/tests/test_review_schemas.py` (new)
- `src/backend/tests/test_reviews.py` (new)
- This report: `docs/developer-tasks/GT-22-GT-25-phase5b-execution-report.md` (new)

## Verification

Local Windows checks from `src/backend`:

- `python -m pytest -m "not postgresql" -q`: **96 passed, 1 skipped, 122 PostgreSQL tests deselected**. The skip is the existing symlink-permission test because symlink creation is unavailable for this Windows account.
- `ruff check app tests migrations`: passed.
- `ruff format --check app tests migrations`: passed.
- `python -m pip check`: passed.
- `python -m compileall -q app migrations tests`: passed.
- `git diff --check`: passed.
- Local PostgreSQL was unavailable (`127.0.0.1:5432` refused the connection), so no PostgreSQL tests are claimed as local passes.

GitHub Actions run [44332102735](https://github.com/MahmoudNagiubX/GradTrack/actions/runs/44332102735) passed on exact head `e64dd2d5b6361fc00f01fd66a46345489a751694`. Its PostgreSQL 16 service applied migrations, all **219 backend tests passed**, Ruff lint and formatting passed, and repository structure checks passed. The initial CI attempt [44331558978](https://github.com/MahmoudNagiubX/GradTrack/actions/runs/44331558978) on `17e7dd4` exposed missing pending-status fallback and an invalid reserved `.test` email in the end-to-end auth test; both were corrected before the passing run.

## Branch, commits, PR, and Jira

**Branch:** `feature/GT-22-25-supervisor-reviews`

**PR #8:** [GT-22 to GT-25 supervisor reviews and resubmissions](https://github.com/MahmoudNagiubX/GradTrack/pull/8), target `develop`, open and not merged.

Commits on this branch:

- `86fcdae169ff40fcfe9e25f1c9f497bb9649bbb5` — `feat(GT-22): add immutable supervisor review APIs`
- `8d57c1a18b7e9c2decb81ff0d4e3ea3050d46569` — `feat(GT-25): append returned submission revisions`
- `366340f3ecd57cb066b1f40da8ba9ce62d83bea9` — `test(GT-22): verify review and revision workflows`
- `17e7dd4bb7379d1058909c92a17b12dac1d456c8` — `docs(GT-22): document Phase 5B review workflow`
- `e64dd2d5b6361fc00f01fd66a46345489a751694` — `fix(GT-22): preserve pending status in version history`

Stack dependencies disclosed on PR #8: PR #2 -> PR #3 -> PR #4 -> PR #5 -> PR #6 -> PR #7 -> PR #8. PRs #2-#7 are still open and require human review in order. Evidence comments were added to Jira GT-22, GT-23, GT-24, and GT-25 with the PR, exact successful CI run, head SHA, and local-versus-CI test results. All four Jira items remain **To Do**; no Jira completion was fabricated.

## Limitations and human action

- Existing private local file storage remains a single-server demo design; there is no antivirus scanning, global upload quota, automated cleanup, or backup service.
- Coordinator visibility is temporarily global and read-only for the single-programme pilot because the schema has no Programme entity.
- Human review and integration of upstream PRs #2-#7 must precede review/integration of PR #8. No merge or Jira Done transition was performed.
- No additional product or architecture decisions are pending for this phase. The next action is human review of the stacked PR chain.
