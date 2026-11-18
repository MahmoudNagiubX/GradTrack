# GradTrack Git and Coding-Agent Workflow

**Applies to:** Mahmoud, all developers, Codex, Antigravity CLI, and other coding agents.  
**Repository:** `MahmoudNagiubX/GradTrack`

## 1. Shared Branch Model

| Branch | Purpose | Direct pushes |
|---|---|---|
| `main` | Protected, release-ready history | Not allowed |
| `develop` | Shared integration branch for completed/reviewed work | Not allowed |
| `feature/*`, `fix/*`, `docs/*`, `test/*` | Isolated task implementation | Task author/agent may push |

All task branches should start from the latest `develop`. A task branch is merged into `develop` only after a human review and required CI checks pass. Releases are promoted to `main` through the agreed release process.

## 2. When to Create a Branch

- Use one branch per Jira task or a tightly related group of tasks.
- Do not create a branch for every tiny edit or every individual commit.
- Do not combine unrelated Jira work in one branch.
- For backend phase work, one branch may cover a clearly bounded phase/step group; keep the commits inside it logically separated.
- If a task has no Jira ID yet, ask the Product Owner to create/link one rather than inventing an issue key.

### Branch naming

```text
feature/GT-20-milestone-submission
fix/GT-21-late-flag
docs/GT-XX-task-spec
test/GT-24-supervisor-approval
```

## 3. Before Editing

1. Confirm the repository and current branch.
2. Run `git status --short`.
3. If unrelated or uncommitted user changes exist, do not overwrite, discard, or stage them. Ask the user how to proceed.
4. Fetch the latest remote state and update local `develop` safely.
5. Create the task branch from `develop`.
6. Read root `agent.md`, the Master Plan, the Jira issue, and the task specification.
7. Inspect nearby code and tests before changing implementation.

Do not run destructive Git commands or reset a user's working tree to make it clean.

## 4. Coding-Agent Implementation

The assigned developer gives the coding agent:

- the Jira issue key;
- the relevant `docs/developer-tasks/GT-XX-*.md` specification;
- any approved design/API references;
- permission to work only within the defined scope.

The agent must:

1. Inspect existing implementation and follow repository patterns.
2. Implement the stated behavior and no unrelated feature work.
3. Add/update tests and documentation.
4. Run the relevant tests, linter, type checks, and build.
5. Inspect the final diff and `git diff --check`.
6. Report any missing requirement or failing check honestly.

If a required product, architecture, security, or paid-service decision is missing, stop and ask. Do not guess.

## 5. Commit Rules

Coding agents **may commit**. Commits should be logical, small enough to review, and large enough to represent a meaningful change.

### Commit format

```text
feat(GT-20): add milestone submission endpoint
fix(GT-21): correct late-submission boundary
test(GT-24): cover assigned-supervisor approval
docs(GT-XX): add developer task specification
refactor(GT-XX): simplify milestone status mapping
```

### Commit checklist

Before each commit:

- [ ] The relevant implementation is complete for that logical unit.
- [ ] Relevant tests/checks have been run.
- [ ] `git status` contains only intended changes.
- [ ] The staged diff has been inspected.
- [ ] `git diff --check` passes.
- [ ] No `.env`, credentials, tokens, real student data, or unrelated files are staged.
- [ ] The configured Git author identity is preserved.

Avoid:
- one giant “implement everything” commit;
- a commit for every trivial line edit;
- misleading commit messages;
- backdated commits or fabricated authorship;
- amending/re-writing already-pushed history without explicit approval.

## 6. Push and Pull Request

After the task is implemented and checks pass:

1. Push the task branch to `origin`.
2. Open a Pull Request targeting `develop`.
3. Include the Jira ID in the PR title/description.
4. Include:
   - purpose and behavior changed;
   - acceptance-criteria checklist;
   - important files changed;
   - tests/checks and their actual results;
   - screenshots or API examples when useful;
   - known limitations and follow-up work.
5. If GitHub CLI/authentication is unavailable, report the branch and provide a ready-to-use PR title and description. Do not claim the PR exists.

The coding agent may create the PR but **must not merge it**.

## 7. Human Review and Merge

A human teammate must:

- inspect the implementation and tests;
- confirm the PR matches the Jira/task specification;
- check that no secrets or unrelated changes are included;
- ask the developer to explain important decisions;
- confirm CI is green and review comments are resolved.

Only then may an authorized human merge the PR into `develop`. Update Jira to reflect the real state. Do not mark a story Done before the team's Definition of Done is satisfied.

## 8. Release to Main

- `main` stays protected.
- Only approved, integrated, release-ready work should move from `develop` to `main`.
- Use the team's agreed release PR/tag process.
- Do not bypass protection or push directly to `main`.

## 9. Backend Phase Commit Examples

```text
feat(GT-XX): initialize FastAPI application
feat(GT-XX): add environment-based settings
test(GT-XX): cover health endpoint
feat(GT-XX): connect PostgreSQL database
feat(GT-XX): add initial Alembic migration
```

Use the actual Jira issue key assigned to the work. The examples do not create Jira issues or imply that these commits already exist.

## 10. Integrity and Safety

- Never fabricate commits, reviews, comments, meetings, votes, tests, or team contributions.
- Never impersonate a teammate in Git author metadata.
- Never backdate activity or rewrite shared history to make work appear earlier.
- Never commit genuine student IDs, real ID-card images, passwords, API keys, or private data.
- AI-assisted work must still be understood, checked, and honestly represented by the assigned developer.

---
*This document supplements the root `agent.md` and the Master Plan. If a conflict appears, stop and ask the Product Owner rather than silently choosing a policy.*