# GradTrack Execution Report — GT-32: User Profile Management Backend

**Date:** 2026-11-21  
**Issue:** `GT-32` — Create an Account and Update a Profile  
**Repository:** `https://github.com/MahmoudNagiubX/GradTrack`  
**Branch:** `feature/GT-32-user-profiles`  
**Base Commit / Verification Head:** `3f6d760b5a6201739bdd52acf94ccbbc23766d15` (PR #12, Phase 7B)  
**Target:** Shared `develop` branch (stacked on PR #12)  
**Agent:** Antigravity CLI  

---

## 1. Verified Source Baseline & Stack Status

- **Upstream PR Status:** PRs #2 through #12 remain open and stacked against `develop` awaiting human peer review.
- **Base Verification:** Branched from `3f6d760b5a6201739bdd52acf94ccbbc23766d15` (Phase 7B latest verified head on `feature/GT-30-in-app-reminders`).
- **Exact-Head CI Baseline:** GitHub Actions Run `44767947594` verified green with 290 passing tests.
- **Local Database Baseline:** Local PostgreSQL 16.11 service running with `gradtrack_dev` and `gradtrack_test` configured.

---

## 2. Product Decisions (Approved D1–D7)

All seven product decisions defined in `GradTrack_GT32_Profile_Backend_Antigravity.md` were approved by the Product Owner and strictly implemented:

- **D1 — Profile Fields:** Authenticated accounts may update `display_name` (nonblank, trimmed, 1–160 chars), plus optional identity fields `student_number` (1–40 chars, letters/digits/`-_/`), `faculty` (1–120 chars), `department` (1–120 chars), `academic_level` (1–40 chars), and `bio` (0–500 chars). All optional fields are nullable and manually entered. `student_number` is an unverified user-entered string and does not confer privileges.
- **D2 — Identity Separation:** Core identity attributes (`id`, `email`, `password_hash`, `system_role`, `is_active`, `created_at`, `avatar_storage_key`) are server-controlled and strictly immutable on profile update. Pydantic `extra="forbid"` rejects any attempt to pass these fields with HTTP 422 Unprocessable Content.
- **D3 — Avatar Constraints:** Strictly PNG/JPG/JPEG up to 2 MiB. Stored in private root `GRADTRACK_PRIVATE_UPLOAD_DIR` using opaque 32-character hex keys. Validates magic bytes (`\x89PNG\r\n\x1a\n` and `\xff\xd8\xff`). Response exposes only `has_avatar: bool`, never internal storage paths or keys.
- **D4 — Read Visibility:** Full self-service profile available via `GET /auth/me`. Teammates, currently assigned active supervisors, and programme coordinators may access a limited teammate profile (`GET /teams/{team_id}/members/{user_id}/profile`) exposing only non-sensitive display attributes (`display_name`, `team_role`, `faculty`, `department`, `academic_level`, `bio`, `has_avatar`). `student_number` and `email` are suppressed. Outsiders, unassigned supervisors, and former supervisors are blocked with HTTP 404.
- **D5 — Avatar Lifecycle:** User can upload, replace, and delete their own avatar. Replacing preserves the old avatar if upload, validation, or DB persistence fails; the old file is deleted only after the new database commit succeeds. Deletion is idempotent and removes the stored file.
- **D6 — Simple API:** PATCH semantics: omitted fields remain unchanged; explicit `null` clears optional fields, while `display_name` cannot be set to `null` or whitespace.
- **D7 — Local-First Scope:** Implemented using existing FastAPI + SQLAlchemy + PostgreSQL + local private file storage. Zero external IAM, CDN, cloud buckets, or ML image processing dependencies added.

---

## 3. Smart Life Planner Read-Only Audit

Audited `C:\Users\mahmo\Desktop\Vscode\Smart Life Planner` (HEAD `f44c4c7fe97a53d03e4df07bbbf42feaf432f9a1`):
- **REUSE:** None directly.
- **ADAPT:** Name trimming, non-empty whitespace validators, and optional field string constraints (`UserProfileUpdate` schema pattern).
- **REFERENCE:** Separation of profile metadata updates from authentication credentials.
- **REJECT:** Async SQLAlchemy session handling, email verification codes, mobile-only local SQLite/photo cache, and Flutter-specific providers.

---

## 4. Endpoints & API Contract

### Authentication & Self-Service (`app/auth.py`)

| Method | Path | Auth | Request Body | Response Model | Description |
|---|---|---|---|---|---|
| `GET` | `/auth/me` | Bearer | None | `UserProfileResponse` | Returns authenticated user profile including academic fields and `has_avatar`. |
| `PATCH` | `/auth/me` | Bearer | `UserProfileUpdateRequest` | `UserProfileResponse` | Updates permitted profile attributes with PATCH semantics (`extra="forbid"`). |
| `POST` | `/auth/me/avatar` | Bearer | Multipart `file` | `UserProfileResponse` | Validates (PNG/JPEG ≤2 MiB), stages, commits, promotes avatar, and removes previous file. |
| `DELETE` | `/auth/me/avatar` | Bearer | None | `UserProfileResponse` | Removes avatar key and deletes file from private storage (idempotent). |
| `GET` | `/auth/me/avatar` | Bearer | None | Binary Stream | Streams caller's own avatar with `image/png` or `image/jpeg` and `nosniff`, `private, no-store`. Returns 404 if no avatar. |

### Team-Scoped Visibility (`app/teams.py`)

| Method | Path | Auth | Request Body | Response Model | Description |
|---|---|---|---|---|---|
| `GET` | `/teams/{team_id}/members/{user_id}/profile` | Bearer | None | `TeamMemberProfileResponse` | Reads limited profile (display name, team role, academic attributes, `has_avatar`). Suppresses `student_number` and `email`. Blocks outsiders/unassigned/former supervisors with 404. |
| `GET` | `/teams/{team_id}/members/{user_id}/avatar` | Bearer | None | Binary Stream | Streams team member's avatar. Returns 404 if missing or unauthorized. |
| `GET` | `/teams/{team_id}` | Bearer | None | `TeamResponse` | Team member list includes `has_avatar: bool` for each member and reflects updated `display_name`. |

---

## 5. Database Schema & Migration

Added additive Alembic migration `src/backend/migrations/versions/gt32_0008_user_profiles.py`:
- **Revision:** `gt32_0008` (down_revision: `gt30_0007`)
- **Columns Added to `users`:**
  - `student_number` (`VARCHAR(40)`, nullable)
  - `faculty` (`VARCHAR(120)`, nullable)
  - `department` (`VARCHAR(120)`, nullable)
  - `academic_level` (`VARCHAR(40)`, nullable)
  - `bio` (`VARCHAR(500)`, nullable)
  - `avatar_storage_key` (`VARCHAR(64)`, nullable)
- **Check Constraints Added to `users`:**
  - `ck_users_student_number_nonempty`: `student_number IS NULL OR length(btrim(student_number)) > 0`
  - `ck_users_avatar_storage_key_len`: `avatar_storage_key IS NULL OR length(avatar_storage_key) = 32`
- **Downgrade:** Drops both check constraints and all 6 columns cleanly; verified with migration test.

---

## 6. Verification & Test Evidence

### Local Test Execution Results

```text
======================= 311 passed, 1 skipped in 49.76s =======================
```
- Total test count: 312 tests collected
- Passed: 311 tests
- Skipped: 1 test (Windows account symlink privilege check, expected and standard)
- Failed: 0
- Non-PostgreSQL unit suite: 128 passed, 1 skipped
- Profile test suite (`test_profiles.py`): 21 passed
- Migration test suite (`test_migrations.py`): 7 passed (including upgrade/downgrade/re-upgrade of `gt32_0008`)

### GitHub Actions CI Verification

- **Exact-Head CI Run:** `https://github.com/MahmoudNagiubX/GradTrack/actions/runs/44844264584`
- **Result:** Success (green checkmark on both `repository-check` and `Backend tests and lint`)
- **CI Test Suite:** `312 passed in 10.81s`
- **CI Lint & Formatting:** `All checks passed!`

### Code Quality & Static Analysis Checks

- `ruff check app tests migrations`: All checks passed!
- `ruff format --check app tests migrations`: 48 files checked, 0 errors!
- `python -m pip check`: No broken requirements found!
- `python -m compileall -q app tests migrations`: Clean compilation!
- `git diff --check`: 0 whitespace or formatting issues!

---

## 7. Git & Pull Request Deliverables

- **Task Branch:** `feature/GT-32-user-profiles`
- **Commits:**
  - `92638a6`: `feat(GT-32): add user profile fields, avatar storage, and team read APIs`
  - `3498fd5`: `test(GT-32): add comprehensive profile, avatar, and migration tests`
  - `5daa692`: `docs(GT-32): document profile APIs, execution report, and advanced roadmap`
  - `82dc4e0`: `test(GT-32): ensure 0o700 permissions on test upload root for posix runners`
- **Pull Request:** `https://github.com/MahmoudNagiubX/GradTrack/pull/13`
- **Status:** Open, targeting `develop`, clearly labeled and documented as **STACKED** on PR #12.

---

## 8. Deviations & Limitations

- **Deviations:** None.
- **Known Limitations:**
  - Local disk storage: Profile photos are stored on the local file system. If the local host crashes between database commit and file deletion of an old avatar, a benign orphaned file may remain in storage.
  - Manual ID entry: `student_number` is a self-reported string without university verification or OCR validation (reserved for future GT-33 spike).
  - No resizing: Avatars are served in their uploaded resolution without client-side or server-side downsampling.

---

## 9. Next Steps

- Await human code review and approval of PR #13 and predecessor PRs #2–#12.
- Do NOT merge any PR automatically.
- Do NOT mark Jira GT-32 Done until acceptance criteria, DoD, and PO review are satisfied.
- **STOP** before Phase 8 (GT-33 or other stories) per operating rules.
