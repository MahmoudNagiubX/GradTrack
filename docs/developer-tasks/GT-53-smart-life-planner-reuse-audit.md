# GT-53 Smart Life Planner Reuse Audit

## Inspected source

- Local reference checkout: `Desktop\Vscode\Smart Life Planner` under the user's profile (resolved at inspection time)
- Revision: `f44c4c7fe97a53d03e4df07bbbf42feaf432f9a1` (`main`, dated 2026-05-07)
- Checkout state: `main` was ahead 2 and behind 1 relative to `origin/main`; an unrelated untracked `docs/mobile_hotspot_demo_run.md` was present and left untouched.
- GradTrack's approved direction remains FastAPI + PostgreSQL with synchronous SQLAlchemy in the current backend. This audit did not modify the reference checkout. `.env` and log contents were not opened or copied.

## Candidate assessment

| Candidate | Classification | Findings, security/compatibility, tests, and effort |
|---|---|---|
| `backend/app/core/security.py` | **REJECT** | Its `hash_password`, `verify_password`, `create_access_token`, and `decode_access_token` use bcrypt/Passlib and `python-jose`, with the key and algorithm supplied by old settings. It conflicts with GradTrack's existing `pwdlib` Argon2id + PyJWT implementation and explicit 32-byte signing-key check. No old tests cover these functions. Copying would replace tested, current GradTrack code; adaptation is unnecessary. |
| `backend/app/api/v1/auth.py` | **REJECT** | Its `get_current_user`, `register`, and `login` sit in a 697-line asynchronous router that also combines email OTP, password reset, Google/Apple sign-in, profile updates, and account deletion. `_generate_code` uses `random.choices`, and registration can return a `development_code`. No manual auth/JWT tests were found. Copying creates substantial scope and security risk; extracting a safe subset would still require a major rewrite. |
| `backend/app/core/dependencies.py` | **REJECT** | Its `get_db` exposes an `AsyncSession` generator. GradTrack uses synchronous SQLAlchemy sessions; switching access mode to copy this helper is explicitly out of scope. No relevant old database tests were found. Adaptation is unnecessary. |
| `backend/app/core/database.py` | **REJECT** | Creates an async SQLAlchemy engine and `async_sessionmaker`, while GradTrack's engine, sessions, models, migrations, and routes are synchronous. The old dependency set also includes both `asyncpg` and `psycopg2-binary`. Do not replace or downgrade GradTrack's existing setup; conversion would be a broad compatibility change. |
| `backend/app/models/user.py` | **REJECT** | Defines `User`, `UserSettings`, and `AuthProvider` around social providers, nullable password hashes, verification/deletion state, and Smart Life Planner preferences. It does not match GradTrack's role/team schema. Timezone-aware timestamp columns use `datetime.utcnow`, which supplies naive UTC values. Copying it would overwrite approved models/migrations and add unrelated fields; no relevant migration test coverage was found. |
| `backend/app/repositories/user_repository.py` | **REJECT** | Its `get_user_by_email`, `get_user_by_id`, `get_user_by_provider`, and `create_user` use `AsyncSession`; `create_user` also creates unrelated settings and commits internally, hiding transaction boundaries. That does not fit GradTrack's synchronous sessions or team-creation atomicity. No user-repository/auth tests were found; adaptation would require a rewrite. |
| `backend/app/schemas/user.py` | **REJECT** | `UserRegister` has an 8-character minimum, conflicting with the approved 16-character policy. `RegisterResponse` exposes an optional `development_code`; the module also bundles OTP/reset/social contracts outside GT-53. Old tests cover some social request validation, not manual auth/password rules. The existing GradTrack schemas are simpler and aligned with the approved contract. |
| `backend/app/services/email_service.py` | **REJECT** | `send_verification_email` / `send_password_reset_email` use a development fallback that logs codes and returns them in `EmailSendResult`; registration then includes the value in its API response. `test_email_service_delivery.py` explicitly expects a returned code. This is sensitive-code disclosure and is not part of GT-53. Do not copy the implementation or its tests. |
| Relevant old authentication/database tests | **REJECT** | No tests for manual `register`/`login`, password hashing, JWT, `create_user`, or database session/migration behavior were found. `test_email_service_delivery.py` codifies code disclosure. `test_apple_sign_in_contract.py` tests Apple/Google request validation, not authentication. |
| `backend/app/services/project_timeline_service.py` and `backend/tests/test_project_timeline_contract.py` | **REFERENCE** | `build_project_timeline`, `validate_timeline_date_update`, and their helpers provide deterministic timeline construction, UTC normalization, overdue/dependency conflict logic, and date-update validation. Five focused tests cover aliases, invalid date order, overdue/conflicts, and dependency boundary violations. Useful for a later timeline/task phase, but project/task assumptions are not a GradTrack team or milestone contract. Revisit after that schema is approved; expected adaptation is moderate and must retain explicit boundary tests. |

## Reuse applied to GT-53

No code or dependency was copied from Smart Life Planner. GradTrack already has the smaller, compatible implementation: Argon2id hashing, PyJWT with explicit HS256 and a short expiry, environment-only signing key validation, server-assigned student role, normalized email, sanitized auth validation errors, and synchronous SQLAlchemy access. Its schema and Alembic migrations were preserved.

The approved password policy is now enforced in both registration and login schemas: minimum 16, current API maximum 128 Unicode characters, spaces and passphrases accepted, and no trimming or truncation. Tests cover 15-character rejection, 16-character acceptance, 64+ Unicode/space-containing passphrases, exact hash verification, and the existing invalid-password case. A repository search found no reliable offline compromised-password blocklist, so no new package or blocklist was introduced.

## Compatibility and security notes

- The reference requirements pin FastAPI 0.111.0, SQLAlchemy 2.0.30, Passlib 1.7.4, bcrypt 4.0.1, `python-jose` 3.3.0, and both async and sync PostgreSQL drivers. These dependencies were not added to GradTrack.
- Static inspection of the old config found a code-defined/default-backed `SECRET_KEY`; no secret value was emitted or copied. Local `.env` files, database dumps, and logs were not opened or copied.
- The email development fallback is unsafe for verification/reset codes because it logs and returns codes, including in a registration response. Its tests confirm this behavior rather than prevent it.
- The old repository tests were inspected but not executed. Reminder/focus/settings modules were not part of this GT-53 reuse review. GradTrack verification is recorded below after each required gate runs.

## Verification and execution record

- Existing database-independent GradTrack baseline before the policy change: `18 passed, 26 deselected` with `src/backend/.venv/Scripts/python.exe -m pytest -m "not postgresql"`.
- Password-policy regression tests were first run against the old minimum and failed at the 15-character rejection boundary (2 expected failures); after changing the request schemas to 16, the focused suite reported `7 passed, 6 deselected`.
- Local final checks: 25 database-independent tests passed, 29 PostgreSQL tests were deselected because no local PostgreSQL service/psql is installed; Ruff lint, Ruff format check, pip check, OpenAPI password bounds, and `git diff --check` passed. The focused password-policy tests first failed at the 15-character boundary, then passed after implementation (7 passed, 6 deselected).
- GT-52 upstream: branch `feature/GT-52-database-foundation`, commit `c79cd9b172ca8d8fa2b4e115d7141de2b598525a`, PR [#3](https://github.com/MahmoudNagiubX/GradTrack/pull/3) open/unmerged. Exact-head CI run [#4](https://github.com/MahmoudNagiubX/GradTrack/actions/runs/44232344489) was observed completed with success during this audit.
- GT-53 branch: `feature/GT-53-manual-auth`; pushed head `896f09ad6b807ead081729eeea09cce77b71d40e`. Commits: `09fbf3a37b27cce72ff4d9d5809e7ad312232169` (implementation), `ec3a789456df9de2ff16bab4ac51ad7418fbbc4f` (tests), `834985c6b4426d1ab75bda2ba7c938337b9016e3` (CI), `896f09ad6b807ead081729eeea09cce77b71d40e` (documentation/audit).
- GT-53 PR [#4](https://github.com/MahmoudNagiubX/GradTrack/pull/4) targets `develop`, is open/unmerged, and is stacked on PRs #2 and #3. Exact-head GitHub Actions run [#5](https://github.com/MahmoudNagiubX/GradTrack/actions/runs/44271516647) passed: 54 tests passed, PostgreSQL migration upgrade passed, and both `Backend tests and lint` and `repository-check` jobs succeeded.
- GT-54 was not started at this audit revision. Its gate passed on GT-53 head `896f09ad6b807ead081729eeea09cce77b71d40e`; create the GT-54 branch from the verified GT-53 head if proceeding.

## Future reuse opportunities

- Revisit the pure project timeline rules and their five tests when GradTrack implements the approved project-task timeline. Map them to GradTrack's own entities and deadline semantics; do not import the Smart Life Planner single-owner model.
- Email, OTP, social sign-in, and password reset remain future candidates only; reminder, focus, and settings modules were not inspected in this review. Any future reuse requires a separate task scope, safe secret handling, and tests for the GradTrack contract. The current email fallback must not be reused as written.

## Remaining blockers and limitations

- Local PostgreSQL is unavailable; the GT-53 PostgreSQL integration suite passed through the configured GitHub Actions PostgreSQL service on the exact pushed head above.
- At this audit revision GT-54 has not started. Its approved rule is coordinator-only supervisor assignment; the current schema has no Programme entity, so coordinator scope is temporarily global for the single-programme pilot. Enforce programme scope if a multi-programme schema is introduced.
- Human review and merge of upstream PRs #2 and #3, and any new GT-53/GT-54 PRs, remain required. No PR is to be merged by this execution.
