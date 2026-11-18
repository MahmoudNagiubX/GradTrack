# GradTrack — Autonomous Backend Execution Runbook
## GT-52 (Phase 1) → GT-53 (Phase 2) → GT-54 (Phase 3, optional)

**Date:** 18 November 2026<br>
**Owner:** Product Owner / Technical Lead<br>
**Repository:** `https://github.com/MahmoudNagiubX/GradTrack`<br>
**Target:** A substantial unattended coding session, not a promise of eight hours of runtime.<br>
**Required agent instructions:** repository-root `AGENTS.md` (exact spelling).<br>
**Status:** Product Owner-approved execution scope once supplied to Codex.

> **Core directive:** Work in strict sequence. Complete a phase, test it, self-review, commit and push organized work, open a PR, verify CI, then start the next phase **only if every gate passed**. Do **not** merge or self-approve PRs, push to `develop`/`main`, fabricate results, or guess missing product decisions.

---

## 0. Current baseline and dependencies

At the last verified GitHub check:

- `develop` contains the merged documentation PR #1 and root `AGENTS.md`.
- Backend Phase 0 is in **open, unmerged PR #2**, branch `feature/GT-51-backend-foundation`, head commit `d7b215b465dd1d10719920c910b99a7ab7b82025`.
- Phase 0 CI passed backend pytest/Ruff and repository structure checks.
- Phase 0 is the FastAPI foundation: health endpoint, config, tests, README and CI; no database, auth or team APIs.
- Phase 0 has not yet received verified human approval. Never merge PR #2 without peer review.
- An old unrelated branch, `docs/update-agents`, exists. Leave it alone.

**Recheck all of these live before beginning.** Read `AGENTS.md`, the Master Plan sections 2, 4, 8, 13–15 and 18, `docs/project/definition-of-done.md`, `docs/project/git-workflow.md`, the existing backend and CI, and the Jira descriptions for GT-51, GT-52, GT-53 and GT-54.

### Important branch strategy

Phase 0 is not in `develop`. Do not invent or duplicate that code. Use this **stacked series of feature branches**:

```text
develop
  └─ feature/GT-51-backend-foundation      [PR #2, open]
       └─ feature/GT-52-database-foundation
            └─ feature/GT-53-manual-auth
                 └─ feature/GT-54-team-management  [stretch only]
```

Branch GT-52 from the verified Phase 0 head; GT-53 from the verified GT-52 head; GT-54 from verified GT-53. Open each PR targeting **`develop`** to trigger the existing CI; state prominently that the PR is **stacked**, that its diff includes predecessor changes, and that it **must not be merged** until earlier PRs merge in order and the resulting diff/CI are reviewed again. Do not auto-rebase, force-push or rewrite existing remote history. If a predecessor merges while working, refetch, inspect and do not assume ancestry.

### Preflight (mandatory)

1. Verify repository identity, current branch, `git status --short`, remotes, Git author, Python version, current branches/PRs, and `gh auth status` when applicable.
2. Stop if unrelated local changes might be overwritten. Do not use `git reset --hard`, `git clean -fd`, or unapproved stashes.
3. The runbook itself can be the **one intentionally new/untracked document**; do not treat it as a conflict. Commit it in a documentation commit as part of GT-52 if appropriate.
4. Verify the Phase 0 branch and its current head CI. Run existing backend tests locally before extending it.
5. Use **synthetic data only**. Do not commit `.env`, passwords, signing secrets, real student records, ID cards or personal details.
6. If missing tools/credentials/decisions require human input, stop safely and record the reason. Do not bypass host security or tool approval mechanisms.

### Common gate after every phase

- Change limited to that phase's approved scope; inspect full diff and staged files.
- Existing earlier phases' tests still pass; new tests pass.
- Ruff lint and format checks pass; `git diff --check` passes.
- Real PostgreSQL integration/migration tests pass when relevant — never substitute SQLite and call it PostgreSQL verification.
- README and OpenAPI reflect real behavior; no fake endpoints or placeholder claims.
- No secrets/unrelated files staged; configured Git identity preserved.
- Meaningful Jira-keyed commits, phase branch pushed, and **PR opened targeting `develop`**.
- GitHub CI **successfully completed for the exact PR head** (do not equate pending or unavailable with passed).
- Write a factual phase summary with tests, CI URL, commits, PR link, blockers.
- **Human review/merge remains pending**; leave Jira at In Progress/In Review, not Done.

If a check fails, attempt a bounded in-scope repair and rerun. If unresolved, **STOP**; do not start the next phase. Do not spend all available time repeatedly refactoring the same failing task.

---

## PHASE 1 — GT-52: PostgreSQL, ORM, Alembic

**Jira:** https://mahmoudnagiub.atlassian.net/browse/GT-52<br>
**Branch:** `feature/GT-52-database-foundation`<br>
**Target:** An actually working, migration-managed persistence foundation.

### Authorized technical choices

For this run, use **PostgreSQL + SQLAlchemy 2.x + Alembic**. Prefer a simple synchronous engine/session unless an existing proven pattern requires otherwise. Use a single consistent data-access approach. Do not introduce Redis, microservices, event buses, CQRS, external hosting, or an unnecessary repository/service abstraction.

### Deliverables

1. A `GRADTRACK_DATABASE_URL` (or consistently named equivalent), loaded from environment, with no production credentials in source. Configuration validation and safe development/test defaults.
2. SQLAlchemy base, session dependency, lifecycle management and connection health integration **without connecting to PostgreSQL during mere module import** or breaking `/health`.
3. Core models and initial migration, **only**:
   - `User`: stable primary key, normalized unique email, password hash storage for Phase 2, display name, system role (`student`, `supervisor`, `coordinator`), active flag, created/updated UTC timestamps.
   - `Team`: stable key, validated name, created/updated timestamps, permits no assigned supervisor.
   - `TeamMembership`: unique `(team_id, user_id)`, user/team FKs, team-scoped `member` or `leader` role, timestamp.
   - `SupervisorAssignment`: team/supervisor reference with explicit single-current-assignment representation and safe reassignment constraints. Supervisor-role validation belongs in domain/service logic, not a bare FK.
4. Document schema choices and explicit constraints. Do not add all conceptual entities from Master Plan §13 at once.
5. Alembic `upgrade head` from empty PostgreSQL and safe downgrade/upgrade in a disposable database.
6. Real PostgreSQL integration tests for constraints, FK enforcement, membership uniqueness, allowed unassigned team, persistence, migration upgrade/downgrade, and Phase 0 regression.
7. GitHub Actions: ephemeral PostgreSQL service for tests; never connect CI to shared/production data.
8. README setup, environment variable examples using placeholders, migrations and test commands.

### Acceptance gate

- All Phase 0 tests and new DB tests pass.
- PostgreSQL integration/migration tests **actually run**, locally and/or through GitHub CI.
- CI on the GT-52 PR passes for exact current head.
- No unauthorized extra domain features or real data.

Suggested logical commits:

```text
feat(GT-52): configure SQLAlchemy and database sessions
feat(GT-52): add core models and Alembic migrations
test(GT-52): verify PostgreSQL constraints and migration lifecycle
ci(GT-52): run PostgreSQL integration tests
docs(GT-52): document database setup
```

**STOP if the database gate fails.** Do not claim success based only on mocks or SQLite.

---

## PHASE 2 — GT-53: Manual Auth, JWT and Role Access

**Jira:** https://mahmoudnagiub.atlassian.net/browse/GT-53<br>
**Branch:** `feature/GT-53-manual-auth`<br>
**Start only when GT-52 gate passed.**

### Scope

1. Manual **student** registration using normalized email, validated display name and password. Assign `student` system role server-side, regardless of user-supplied role fields.
2. Password hashing/verification with maintained **Argon2id** implementation. Never store or return plaintext passwords.
3. Short-lived signed JWT bearer access tokens using maintained library, explicit algorithm and correct expiry verification.
4. Require a securely configured signing key for actual runtime auth; no hardcoded production secret and no per-request generated signing key. Tests/CI may use explicit synthetic secrets.
5. Implement consistent FastAPI endpoints (unless existing conventions dictate equivalent):
   - `POST /auth/register`
   - `POST /auth/login`
   - `GET /auth/me`
6. Reusable authenticated-user and system-role authorization dependencies with server-side checks. **Team leader is a per-team membership role, not a global system role.**
7. Test-only seed/fixture path for supervisor/coordinator accounts; **no public privileged-role creation or elevation endpoint**.
8. Appropriate validation, duplicate handling, disabled user behavior, safe error messages and OpenAPI schemas.
9. Keep `/health` available without authentication.

### Explicitly out of scope

Google OAuth/OIDC, email OTP, university ID OCR, refresh-token service, password reset flows, frontend/mobile, avatars, email/phone identity verification, Redis.

### Mandatory security tests

- Valid registration persists a **hash**, not plaintext.
- Invalid/duplicate email and weak/invalid input rejected.
- Login succeeds for valid student; `/auth/me` returns permitted fields only.
- Wrong password/unknown user does not leak credentials or hashes.
- Missing, invalid, tampered and expired JWT denied.
- Disabled users rejected, including with previously issued token.
- Student cannot register as supervisor/coordinator or make itself a team leader.
- Unauthorized role access denied.
- Existing `/health`, DB constraints, migration and lint tests still pass.

### Acceptance gate

All security/auth tests plus regression and CI green at the phase head. No credential leakage or privilege-escalation path. PR created, pushed, correctly labeled stacked and awaiting human review.

Suggested commits:

```text
feat(GT-53): implement secure student registration
feat(GT-53): add JWT login and current-user endpoint
test(GT-53): cover authentication and role-denial cases
docs(GT-53): document authentication API
```

**STOP if the auth gate fails.** Do not start teams with a broken identity layer.

---

## PHASE 3 — GT-54: Teams and Supervisor Assignment (Stretch Only)

**Jira:** https://mahmoudnagiub.atlassian.net/browse/GT-54<br>
**Branch:** `feature/GT-54-team-management`<br>
**Start only when GT-52 and GT-53 gates passed and no material blocker remains.**

### Functional scope

1. **GT-15 Create Team**
   - Authenticated student creates a team with validated nonempty name.
   - Creator becomes its first `leader`/member **atomically**.
   - Lists and reads only authorized team data.

2. **GT-16 Add Members**
   - Authorized team leader adds an existing valid student member.
   - Prevent duplicate membership; reject out-of-team modifications.
   - Keep invitations, university directory integrations, email/OTP out of scope.

3. **GT-17 Supervisor Assignment**
   - Track team's currently assigned supervisor.
   - **Students and team leaders must not assign their own supervisor.**
   - If the Master Plan/Jira explicitly establishes programme-coordinator assignment permission, implement and test that approved path.
   - If assignment/reassignment authority is ambiguous, **do not improvise it**. Finish only independent team operations, note missing GT-17 and stop this phase as partial.
   - Assigned supervisors see only their assigned teams; others cannot enumerate or access them.

4. HTTP contracts should remain small and testable. No React/Flutter screens, milestones, submissions, approvals or file uploads in this phase.

### Mandatory tests

- Team creation with creator membership/leader permissions in one transaction.
- Empty name and duplicate membership failures.
- Membership/assignment cross-team authorization denial.
- Listing only permitted teams.
- Unauthorized student supervisor-assignment attempt rejected.
- Coordinator assignment when formally authorized.
- Assigned vs unassigned vs wrong-supervisor read access.
- Database rollback/atomicity, plus Phase 0–2 regressions.

### Acceptance gate

All relevant tests and PostgreSQL checks green; PR exists, branch pushed, upstream dependencies disclosed, no auto-merge. If incomplete, report partial status explicitly.

Suggested commits:

```text
feat(GT-54): implement team creation and membership
test(GT-54): verify team isolation and transaction integrity
feat(GT-54): implement authorized supervisor assignment
test(GT-54): enforce assigned-supervisor boundaries
docs(GT-54): document team APIs and limitations
```

**Do not start Phase 4 or any other feature without a new approved plan.**

---

## Git, PRs and review discipline

The resulting Git branches will be stacked until predecessor PRs merge. This is intentional for development continuity, but must be clear to reviewers.

For **each** phase:

- Commit only changes relevant to the phase.
- Push only its feature branch.
- Open PR to `develop` so existing CI triggers.
- PR title begins `[GT-52]`, `[GT-53]`, or `[GT-54]`.
- PR body names upstream PR(s), and states: **"STACKED PR: do not merge until predecessors are human-reviewed and merged; re-check diff and CI afterward."**
- List exact test commands, actual results, migrations performed, security test coverage, known limitations and CI URL.
- **Never merge PRs yourself.** Human team review is mandatory.
- Do not mark any Jira issue `Done` before peer review, merge and team DoD. If Jira connection is available, `In Progress` or `In Review` is fine when truthful.
- If GitHub authentication or PR creation fails, preserve local commits, report exact error, and do not claim PR/CI completion or advance through a missing gate.

### Safe stop conditions

STOP when: unexpected local modifications; missing Phase 0 baseline; unapproved architecture or product ambiguity; missing PostgreSQL verification; unresolved failing tests; remote branch divergence; absent secrets needed for runtime; CI unavailable/failing; credential or privacy risk; unresolved security bug; need for destructive/admin actions.

Do not reset, force-push, disable checks, impersonate a teammate, invent CI passes, or continue into a dependent phase after an incomplete prerequisite.

---

## Required final handoff

Write an accurate report under `docs/developer-tasks/GT-52-GT-54-execution-report.md` in the **latest phase branch**, and print it in the Codex chat:

```text
Starting state:
- Branch / HEAD / Phase 0 PR:
- Existing environment / constraints:

GT-52 / Phase 1:
- Status (not started / partial / locally verified / CI passed / PR open):
- Branch and commits:
- PR URL:
- DB models and migrations:
- Actual PostgreSQL test commands/results:
- CI URL and result:
- Known issues:

GT-53 / Phase 2:
- Status:
- Branch and commits:
- PR URL:
- Endpoints and permissions:
- Security tests/results:
- CI URL and result:
- Known issues:

GT-54 / Phase 3:
- Status:
- Branch and commits:
- PR URL:
- Team/supervisor behaviors:
- Authorization tests/results:
- CI URL and result:
- Known issues:

Overall:
- Upstream PR dependencies and merge order:
- Uncommitted changes:
- Checks not run:
- Decisions/blockers requiring human approval:
- Jira status (verified, not invented):
- First action required from the human reviewer:
```

If work stops after GT-52, say so; do not claim GT-53 or GT-54 were done.

## Start Codex with this exact message

```text
Read AGENTS.md and docs/developer-tasks/GT-52-to-GT-54-autonomous-runbook.md fully.
This runbook is the approved scope for this unattended GradTrack backend work.

Implement GT-52 first, then GT-53 only after all GT-52 verification and CI gates pass,
then GT-54 only after GT-53 passes and no blocker remains.

Inspect current GitHub/branch state. PR #2 for GT-51 was last seen open and unmerged:
do not merge it. Use the runbook's stacked branch strategy.
Make organized commits, push only task branches, create PRs to develop, review your own
diffs, run real tests including PostgreSQL, and wait for GitHub CI results.
Never self-merge or push to main/develop. Stop on ambiguity, failures or missing approvals.
Record a factual execution report with all branch/commit/PR/check links.

Do not implement Phase 4 or beyond. Work sequentially while the local session permits.
```

## Windows unattended operation — read before sleeping

- The Codex CLI process must remain active and able to access its configured tools.
- Keep the laptop connected to power and **prevent Windows from entering Sleep/hibernate** for the intended unattended period; a lock screen is fine if it does not suspend the machine.
- Keep VS Code/terminal running and the internet connection stable.
- Approval prompts, expiring credentials, tool/network failures and session limits can still stop work. Do not disable safety checks or grant broader system access just to make it run unattended.
- Do not assume this document launches a cloud agent or guarantees continuous execution for eight hours.

**Success criterion:** one or more verified, reviewable backend phases with real tests and clean PR history — not necessarily all three phases completed.
