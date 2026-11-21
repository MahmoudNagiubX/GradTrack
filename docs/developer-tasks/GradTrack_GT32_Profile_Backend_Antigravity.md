# GradTrack — GT-32: Profile Management Backend

**Antigravity CLI implementation contract | Flash 3.8 High (user-selected)**  
**Date:** 2026-11-21  
**Repository:** `https://github.com/MahmoudNagiubX/GradTrack`  
**Issue:** `GT-32` — Create an Account and Update a Profile  
**Target:** Python FastAPI + PostgreSQL + existing private local file storage on one Windows laptop  
**Scope:** Backend only; **do not** implement React, Flutter, OCR, Google Sign-In, email OTP, or other advanced modules in this task.

## 1. Objective and Jira acceptance criteria

Existing Phase 2 manual registration and login already satisfy part of GT-32. Complete the missing profile functionality, including **authorized editing of permitted fields and profile photo management**, while preserving the server-controlled system role and existing authentication behavior.

Jira GT-32 acceptance criteria:
1. A student can register and sign in securely — **already implemented; regression-test, do not rewrite**.
2. A student can update allowed profile details and photo — **implement**.
3. A student cannot change their own system role — **enforce server-side and test**.

Master Plan §5.1 additionally describes student/university ID, faculty, department/specialization, level, team/project role display, optional bio and avatar. Do not claim OCR verification, academic eligibility or university record authenticity based on user-editable fields.

## 2. Verified source baseline — refresh before working

- GitHub PR #12: `https://github.com/MahmoudNagiubX/GradTrack/pull/12` is **OPEN and unmerged** at last check, latest actual head: `3f6d760b5a6201739bdd52acf94ccbbc23766d15` on `feature/GT-30-in-app-reminders`.
- Exact-head CI: `https://github.com/MahmoudNagiubX/GradTrack/actions/runs/44767947594` — two checks successful; last report records 290 passing tests with PostgreSQL 16 in CI.
- Local Demo report from user: Windows PostgreSQL 16.11 working; `gradtrack_dev` and `gradtrack_test` migrated to `gt30_0007`, 289 tests passing + one Windows symlink-permission skip, complete local HTTP student/supervisor flow and persistence verified. **Verify current local state rather than assuming it never changed.**
- PRs #2–#12 remain open and stacked as of last inspection. Human approval is **deferred, not waived**. Existing team git-workflow says branches from `develop`; the PO previously authorized an exceptional stacked approach. For this task, the PO explicitly authorizes basing a **new** task branch on the latest verified Phase 7B head if those PRs are still pending. Never merge them automatically.
- Existing `src/backend/app/models.py::User`: `id, email, password_hash, display_name, system_role, is_active, created_at, updated_at`. No avatar or academic-profile fields.
- `app.auth` has `POST /auth/register`, `POST /auth/login`, `GET /auth/me`, JWT dependency. `app.schemas.PublicUser` exposes only id/email/display_name/system_role.
- `app.submission_storage` already supports local private staged files, opaque keys, validation, safe opening. Reuse or narrowly extend its existing operations instead of creating a second file-storage service.
- `src/backend/migrations/versions/gt30_0007_notification_reads.py` is the current schema tip. Add **a new additive Alembic revision after it**; do not edit applied migrations or previously delivered contracts.

Read root `AGENTS.md`, Master Plan §5.1 and priorities, Jira GT-32, `docs/project/definition-of-done.md`, `docs/project/git-workflow.md`, recent backend execution reports, current auth/storage routes/models/schemas/tests, and this spec. Read the exact local working tree first; preserve user changes.

## 3. Product decisions — approve explicitly before implementation

These choices are a proposed small, course-project profile contract. They are approved **only** if the PO explicitly approves D1–D7 in the accompanying Antigravity startup instruction. Stop and report if Jira/Master Plan, later decisions or actual code conflict materially.

**D1 — Profile fields:** An authenticated active account may update `display_name` (nonblank, trimmed, max 160 chars), plus optional `student_number`, `faculty`, `department`, `academic_level`, `bio` (all bounded, trimmed and nullable). Keep optional identity fields simple strings: no new faculty/department/programme tables. For demo, permit **manual** entry and correction; `student_number` is NOT a verified ID, credential or authorizing claim. Do not infer eligibility or restrict access using these fields.

**D2 — Identity separation:** Server owns immutable/privileged properties for the self-service route: `id`, `email`, `password_hash`, `system_role`, `is_active`, `created_at`, membership/leader roles and supervisor assignment. They must not be writable through profile JSON (Pydantic `extra=forbid`). Email/password changes and recovery are distinct future tasks. `GET /auth/me` remains backward compatible and adds optional fields rather than deleting existing ones.

**D3 — Avatar:** One current avatar per user, **PNG/JPG/JPEG only**, maximum **2 MiB**, no SVG/GIF/video. Use existing private upload root `GRADTRACK_PRIVATE_UPLOAD_DIR`, server-generated opaque storage keys, image content checks and safe failure handling. Do not embed base64 images in PostgreSQL, create public/static upload folders, integrate cloud services or add a photo-processing dependency merely for this demo. Return a safe `has_avatar` flag, never a private storage key/path.

**D4 — Read visibility:** Every user may read their own full (nonsecret) profile through `GET /auth/me`. Members of the same active team, its currently assigned active supervisor and programme coordinator (current pilot scope) may see a **limited teammate profile** through a team-scoped endpoint; only non-sensitive display fields (name, faculty, department, academic level, avatar flag) are disclosed there. Student number and private self-service fields stay on `GET /auth/me` by default. No public unauthenticated profile route. Former supervisor/unrelated team student cannot fetch photos or metadata.

**D5 — Avatar lifecycle:** User can upload/replace/delete **their own** photo. Replacing should preserve the old avatar if validation/DB commit fails; delete old file only after new metadata commits. Deletion removes the profile pointer; best-effort cleanup is acceptable on this single-machine demo, with crash-orphan limitations reported honestly. Avoid unrelated file deletion and path traversal. No avatar edit history or permanent photo retention requirement.

**D6 — Simple API:** Use PATCH semantics: omitted field = unchanged; explicit `null` clears optional field, but cannot clear required display_name. Use existing bearer JWT, SQLAlchemy session and FastAPI patterns. No new external service, generic account settings engine, role provisioning or automatic avatar resizing.

**D7 — Local-first scope:** The project will be demonstrated with synthetic accounts and private local files. Do not overengineer production-ready IAM, CDN, background jobs, email services or cloud storage. Preserve authorization and basic upload safety because those are essential for a correct working demo.

### Validation defaults proposed within D1

- `student_number`: 1–40 chars when present; letters, digits and limited separators (`-`, `_`, `/`) are acceptable, whitespace trimmed; no uniqueness/verification guarantee.
- `faculty`, `department`: 1–120 chars when present; permit English and Arabic Unicode text.
- `academic_level`: 1–40 chars when present; free text because programme-specific levels aren't modeled yet.
- `bio`: 0–500 characters when present; trim. Empty optional strings normalize to `null` if consistent with existing validation.
- Nullable academic/profile data must not silently change `User.system_role`, team leadership or any permission.

If implementation uncovers an actual uniqueness/validation requirement from the Master Plan or Jira, flag the conflict rather than silently inventing a rule.

## 4. Implementation plan (bounded)

### 4.1 Migration and model

- Add nullable profile fields and an `avatar_storage_key` (or similarly private column) on `users`; prefer a focused additive migration named e.g. `gt32_0008_user_profiles` with down_revision `gt30_0007`.
- Keep existing rows and login/password hashes intact; no user records deleted or recreated. Consider reasonable length/check constraints consistent with Pydantic; don't pile on unnecessary DB indexes for columns not queried.
- No separate Profile table is required for this local MVP unless actual schema constraints demand one.
- Validate upgrade, downgrade and re-upgrade on a disposable **test** PostgreSQL DB, especially preserving preexisting accounts/teams/submissions; don't downgrade the user's dev database as an experiment.

### 4.2 Schemas and authorized self-service API

- Add focused profile PATCH request and response schemas (Pydantic `extra=forbid`, validators, `model_fields_set` to distinguish omit from explicit null).
- `GET /auth/me` should return self-service profile data, keeping existing id/email/display_name/system_role fields and nonsecret academic attributes; no password hash, token, storage key or other users' private info.
- `PATCH /auth/me`: update only caller's permitted fields; active authentication required; empty body a no-op. Preserve existing Auth patterns and clear 401/422 responses. Prefer no account-role changes whatsoever.
- `POST /auth/me/avatar`: multipart single `file`, validate bytes/MIME/extension/content and 2 MiB limit, stage + promote privately; return updated safe profile metadata.
- `DELETE /auth/me/avatar`: clear own photo with sensible idempotent behavior. Do not delete milestone or task attachment files.
- Optional `GET /auth/me/avatar` for own preview; where included, avoid duplicate storage logic.

### 4.3 Team-safe profile and avatar reads

- `GET /teams/{team_id}/members/{user_id}/profile`: authenticate and call existing `get_visible_team`, then verify requested user is a current member of that exact team; return a limited display-only profile. Include photo availability flag and existing team role as **display**, not a new mutable system role.
- `GET /teams/{team_id}/members/{user_id}/avatar`: same team visibility and membership checks, stream the avatar with correct `image/png` or `image/jpeg` content type and safe `Content-Disposition` / `nosniff` / `no-store`; no filesystem paths or storage keys disclosed. A missing avatar returns 404.
- Respect former-supervisor restrictions, unrelated team access and coordinator's current pilot-global scope; don't broaden visibility globally by user ID.
- Ensure existing team-list member display names remain current after a profile name change; if needed, add optional `has_avatar` to `TeamMemberResponse` without breaking callers.

### 4.4 Private file reuse

Inspect `app.submission_storage.stage_upload`, `_validate_file_contents` and `open_stored_file` before changes. Current shared storage supports docs/images up to 20 MiB. For avatar route enforce **strict subset** (PNG/JPEG, ≤2 MiB), ideally by a **backward-compatible optional max-size/type constraint** or a tiny validated wrapper, not by copying hundreds of lines or relaxing existing checks. Do not trust a filename/MIME claim alone. Do not write real face photos to repo or CI.

Ensure failure to store/retrieve avatar returns a safe status and leaves existing avatar metadata intact. Recheck current account/permissions during write where necessary. An oversized streaming upload must be rejected without unbounded buffering. No client-controlled file destination. Keep old photo until new DB commit succeeds; document any best-effort orphan-file edge instead of adding a janitor service.

### 4.5 Smart Life Planner reuse audit (read-only)

Inspect `C:\Users\mahmo\Desktop\Vscode\Smart Life Planner` if available (previously reported HEAD `f44c4c7fe97a53d03e4df07bbbf42feaf432f9a1`) for narrowly relevant profile/avatar validation and serving. Record actual HEAD and REUSE/ADAPT/REFERENCE/REJECT decisions; do **not** import its async SQLAlchemy/auth/session code, email fallback, secrets or entire media subsystem. Prefer GradTrack current patterns.

## 5. Acceptance checklist and test matrix

1. Existing registration/login/`GET /auth/me` JWT contract remains valid and backward compatible.
2. Authenticated active user changes display_name and each optional academic field. Subsequent GET and fresh login reflect persisted changes.
3. Clearing optional field via explicit null works; omitted fields remain unchanged; invalid blank display_name and oversized fields return 422.
4. Requests including `system_role`, `is_active`, `id`, `password_hash`, `email`, team leader/assignment changes, `avatar_storage_key` are rejected; role remains unchanged in DB.
5. PNG/JPEG avatar upload (valid test-generated bytes) works; only allowed formats and ≤2 MiB accepted. Spoofed extension/MIME and invalid/oversized image fail.
6. Replacement preserves original avatar when upload/DB persistence fails; successful replacement displays new file; delete is safe/idempotent. Other users' avatars, milestone submissions and task attachments remain intact.
7. `GET /auth/me` never reveals private storage paths/keys or password hashes. Team-scoped profile/avatar read shows only permitted fields and image; unrelated users, removed members, former supervisors are blocked.
8. Existing coordinator and supervisor access stays read-only; they cannot mutate another user's profile through self-service route.
9. Profile fields, photo and authenticated download persist across FastAPI restart; use existing synthetic local demo workflow if possible.
10. Alembic migration upgrades/downgrades safely in test DB and preserves existing users. PostgreSQL regression suite on exact-head PR CI remains green.
11. Windows local photo root configured and verified; no real university photos uploaded to repo/screenshots/tests.
12. Profile APIs visible/accurate in `/docs`, README updated. No unintended changes to phases 0–7B.

Tests should be added in focused `tests/test_profiles.py` plus existing `test_auth.py`, `test_migrations.py`, storage tests as necessary. Test non-PostgreSQL unit validations and **real PostgreSQL 16 integration**; manually exercise an HTTP upload and authenticated image read on the working local laptop. Document exact numbers, not assumed counts.

### Standard checks (actual environment/venv may differ)

From `src/backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest -m "not postgresql"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\ruff.exe check app tests migrations
.\.venv\Scripts\ruff.exe format --check app tests migrations
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q app tests migrations
```

For integration tests use a dedicated database URL whose name ends in `_test`, and ensure the known development database is not used. Validate actual migrations, `git diff --check`, final staged diff, `git status`. Do not claim tests passed if not run.

## 6. Git / Jira / reporting discipline

- First verify latest PR #12 head and CI; if still stacked, create **new** `feature/GT-32-user-profiles` from latest verified Phase 7B branch head. **Do not** develop on shared `develop` or existing Phase 7B task branch.
- If previous PRs are genuinely peer-reviewed and merged by then, use fresh integrated `develop` instead of stacking.
- No direct commits to `main`/`develop`, auto-merge, force-push, history rewrite, fake contributor attribution, or fabricated Agile ceremonies.
- Logical commits e.g. `feat(GT-32): add self-service profile fields`, `feat(GT-32): add private avatar upload and team reads`, `test(GT-32): cover profile authorization and migrations`, `docs(GT-32): document profile API`.
- PR targets `develop` and is labeled/clearly described as **STACKED** with predecessors #2–#12. Do not request or claim a real human approval on behalf of anyone. Jira may move from To Do to In Progress during actual work, then In Review after evidence; **do not mark Done** until agreed DoD, peer review, merge and PO acceptance.
- Keep implementation to the task. No OAuth2 client, SMTP/OTP, OCR library, face recognition, image ML, cloud provider, frontend route, UI or unrelated refactor.

### Required execution report

At `docs/developer-tasks/GT-32-profile-backend-execution-report.md`, report:

- Starting branch, latest GitHub SHA, local dirty/clean state, dependencies and stack status.
- Explicitly approved D1–D7 and any actual conflicts.
- Smart Life Planner read-only audit and reuse reasoning.
- Files changed, migration, data/permission decisions, API paths and examples.
- Photo constraints, ownership, access, replacement/deletion behavior and local storage limitations.
- PostgreSQL/local HTTP tests, full regression, CI **exact-head** SHA/run URL, lint/migration commands with real pass/fail counts.
- Commits, pushed branch, opened PR, Jira evidence/status and outstanding reviewer/merge gate.
- Remaining blockers; do not begin GT-33, GT-34 or any other advanced story automatically.

## 7. Suggested Antigravity CLI startup prompt

```text
Read root AGENTS.md, docs/Graduation_Project_Tracker_Master_Plan.md §5.1,
Jira GT-32, and docs/developer-tasks/GradTrack_GT32_Profile_Backend_Antigravity.md
completely. Follow the existing project git-workflow and task template.

I explicitly APPROVE GT-32 proposed product decisions D1–D7 in this specification.
I authorize GT-32 BACKEND IMPLEMENTATION ONLY on a new feature branch based
on the latest verified Phase 7B head if earlier PRs remain unmerged. This
is a stacked-development exception, NOT permission to merge any PR.

Implement self-service profile editing, optional manually entered academic
fields, private PNG/JPEG profile photo upload/replacement/deletion, and
team-scoped safe profile/photo reads. Preserve current registration/login,
JWT authorization and all old APIs. Never permit self-changing system roles.

Reuse existing GradTrack local private storage and audit Smart Life Planner
read-only; avoid production infrastructure and unrelated features.

Run actual local PostgreSQL 16 regression/integration tests, verify real
HTTP profile/photo persistence, run lint/migrations and exact-head GitHub CI.
Fix confirmed in-scope bugs; document results honestly. Commit and push the
new task branch, open a clearly stacked PR to develop, update Jira evidence,
then STOP. No merge, no Done status, no frontend and no next advanced story.
Return a factual report with exact commit SHA, PR/CI links and outstanding items.
```
