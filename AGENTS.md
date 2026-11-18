# AGENT.md — GradTrack Agent Operating Rules

> **Applies to:** Codex, Antigravity CLI, and other coding agents working in this repository.<br>
> **Core rule:** You are implementing an already-approved product specification. You are not designing a new product.

These rules apply to every agent task unless the human Product Owner explicitly approves a specific exception. A task-specific instruction may narrow the work, but it cannot silently override the approved product scope, security rules, or protected Git workflow.

---

## 1. The Master Plan Is the Product Source of Truth

Before implementing product behavior, read:

`docs/Graduation_Project_Tracker_Master_Plan.md`

Also read the relevant Jira issue and the assigned developer-task specification under:

`docs/developer-tasks/`

The Master Plan defines the approved product vision, requirements, business rules, feature priorities, and course constraints. A later explicitly approved Master Plan revision or Product Owner decision supersedes an earlier statement.

**Current approved application direction:**

- **React** is the primary and complete web application.
- **Flutter** is the focused mobile companion application; it does not need to reproduce every web feature.
- **FastAPI + PostgreSQL** are the shared backend direction for both clients.
- Both clients use the same backend API and persisted data.
- A change made through one client becomes visible to the other when it fetches or refreshes data. Do not claim WebSocket, push, or offline synchronization unless separately implemented and verified.
- Smart Life Planner is a reference project for selective reuse, not a replacement product or a codebase to copy wholesale.

You must not silently reinterpret, weaken, remove, or expand approved behavior.

If the Master Plan does not define something that affects product behavior, stop and ask the human Product Owner. Do not fill gaps with assumptions.

---

## 2. No Product Improvisation

You must not independently:

- add a feature that is not part of the assigned task or approved scope;
- remove an approved feature because it seems unnecessary;
- change an approved user journey or business rule;
- change who can view, create, edit, submit, review, or approve data;
- change role permissions or team ownership rules;
- change the meaning of a project status, deadline, progress metric, or report;
- turn a planned/manual workflow into an automated one without approval;
- redesign the product because another approach seems cleaner or more impressive.

If a product-affecting decision is unclear, **STOP and ask**.

Use this format when useful:

```text
Decision needed:
Why it is unclear:
Options, if useful:
What is currently blocked:
```

Do not resolve product ambiguity by guessing.

---

## 3. Task Specification Is the Implementation Contract

Before implementation, identify:

```text
Task / Jira issue:
Task specification:
Files expected to change:
Master Plan sections involved:
Out of scope:
Acceptance criteria:
```

For bounded work assigned to a developer and coding agent, use a task file based on:

`docs/developer-tasks/TASK_TEMPLATE.md`

The task specification should define the objective, user value, current implementation context, in-scope behavior, explicit exclusions, acceptance criteria, edge cases, tests, security constraints, and expected deliverables.

If a task file conflicts with the Master Plan, or omits a decision necessary for correct product behavior, stop and ask. Do not silently change the specification to make an incomplete implementation appear complete.

Large or cross-cutting features must be broken into phases or smaller tasks before implementation. Do not accept vague instructions such as “build the whole backend” or “make the dashboard better” as sufficient implementation contracts.

---

## 4. Minimal-Change Rule

Change only what the assigned task requires.

For example, if the task is to implement milestone submission, do not also redesign:

- authentication;
- the entire database schema;
- unrelated dashboards;
- unrelated task-management flows;
- the frontend architecture;
- notification delivery;
- other APIs or UI components.

If an out-of-scope change is genuinely necessary:

1. stop before making it;
2. explain why it is needed;
3. identify the affected files/components and risks;
4. ask the human developer for approval.

Do not hide unrelated changes inside a larger task. Small tasks should produce small, understandable diffs whenever possible.

---

## 5. No Unnecessary Files or Cosmetic Architecture

Do not create files or folders only for cosmetic organization.

Avoid unnecessary files such as:

```text
helpers.py
utils.py
constants.py
config2.py
temp/
legacy/
backup/
new_version/
final_v2/
misc/
```

These are examples, not a complete blacklist. A file is appropriate when it has a clear responsibility and belongs in the existing project structure.

Before creating a file:

1. inspect the existing repository structure;
2. search for an appropriate existing module or component;
3. check whether the behavior can be added cleanly to an existing file;
4. create a new file only when it improves clarity, cohesion, or maintainability.

Do not create duplicate versions of existing files. Do not split simple logic across many tiny files just to look architecturally sophisticated.

---

## 6. No Premature Architecture

Do not introduce major infrastructure, patterns, or frameworks without explicit approval from the technical architecture owner / Product Owner.

Examples include:

- microservices;
- event buses or message brokers;
- Kafka;
- Redis;
- Kubernetes;
- complex distributed systems;
- CQRS;
- large abstraction layers;
- unnecessary service boundaries;
- framework or database migrations;
- additional authentication providers;
- new paid third-party services.

Use the simplest architecture that matches the approved Master Plan and the repository's existing implementation.

If a major architectural change appears necessary, explain the technical reason, affected components, alternatives, and risks. Ask before implementing it.

Do not interpret the presence of a technology in an old reference project as approval to add it to GradTrack.

---

## 7. Inspect Before Building; Reuse Carefully

Before implementing a non-trivial subsystem:

1. inspect the current GradTrack repository and relevant existing code;
2. search for existing endpoints, components, models, utilities, tests, and patterns that may already solve the problem;
3. inspect the Smart Life Planner reference project only when relevant;
4. where necessary, research proven technical approaches or authoritative documentation;
5. understand a candidate implementation before adapting or reusing it;
6. check compatibility, dependencies, security, licensing, and test coverage.

Important:

**A repository or library found elsewhere is an implementation reference. It does not authorize changing GradTrack's approved product behavior or architecture.**

Do not copy a large unknown codebase into GradTrack. Do not copy secrets, `.env` files, developer logs, sample personal data, or unrelated modules from Smart Life Planner.

External research must support the approved task; it must not become an excuse to redesign the product.

---

## 8. Protect Existing Working Functionality

Never remove or replace working behavior simply because a new implementation looks cleaner.

Before replacing or deleting existing behavior:

- understand what it currently does;
- identify its callers and dependencies;
- identify API, data, and UI contracts;
- verify the replacement covers all required behavior;
- add or update regression tests;
- run relevant verification.

A cleaner implementation is not automatically a correct replacement.

Do not reformat, rename, reorder, move, or rewrite unrelated files. Do not “clean up the whole project” during a focused feature task.

---

## 9. Preserve Existing Contracts

Before changing an existing contract, identify its consumers.

Contracts include:

- API request and response shapes;
- shared database schemas and persisted data formats;
- function signatures used across modules;
- authentication and authorization behavior;
- frontend/backend integration points;
- shared state structures;
- file upload and download behavior.

If a task requires a breaking or material contract change, stop and report:

```text
Contract change required:
Reason:
Affected components:
Proposed change:
Migration / compatibility impact:
```

Get approval when the change may affect another developer's work, another subsystem, or existing persisted data.

Do not casually break frontend/backend integration while improving one side.

---

## 10. GradTrack Business Rules and Authorization

Enforce approved business rules on the backend, not only in the UI.

1. A submission after its applicable deadline is marked **Late**. A submission on or before the deadline is not late.
2. Only the team's currently assigned supervisor may approve that team's submission.
3. Students cannot approve their own submissions or change their supervisor assignment.
4. Team data, submissions, attachments, and files must be isolated from other teams.
5. Users cannot self-grant supervisor, coordinator, or team-leader permissions through editable profile fields.
6. Every protected backend operation must verify the user's identity, role, team membership, and permission for that specific resource/action.

When a task touches these rules, add tests for both allowed and forbidden actions. Include deadline boundary cases when relevant.

If the exact behavior is not defined by the Master Plan or task, ask instead of inventing a new rule.

---

## 11. No Fake Implementations, Placeholders, or Integrations

Do not claim a feature is implemented when it is only a placeholder, hardcoded label, stub, or misleading demo shortcut.

Unacceptable examples when presented as completed functionality:

```python
return "AI generated plan"
pass
raise NotImplementedError
# TODO: implement later
mock_response = "success"
```

Mocks and stubs are acceptable only when the assigned task is explicitly a scaffold/prototype step or the product specification explicitly defines a simulated boundary.

For every simulated or mocked integration:

- label it clearly as simulated/mock;
- state what is and is not connected;
- do not present it as a live external service;
- keep the boundary visible in the code and completion report.

A completed feature must have, where applicable:

- real logic;
- defined inputs and outputs;
- validation and permission checks;
- failure/error handling;
- persistence when required;
- tests or a reproducible demo path.

If only part of a feature is implemented, report exactly which part.

---

## 12. Avoid Dependency Spam

Do not add a package for trivial functionality that can be implemented clearly with existing dependencies or the standard library.

Before adding a dependency:

- confirm that it provides meaningful value for the assigned task;
- check whether the repository already has an equivalent dependency;
- check maintenance, compatibility, licensing, and security;
- explain why it is needed.

Do not add multiple libraries that solve the same problem without a clear reason. Do not change the chosen framework or dependency strategy without approval.

---

## 13. Security and Privacy

- Use synthetic/test data only in the repository, tests, CI, screenshots, and demos.
- Never commit genuine student records, real university ID images, extracted real ID details, real phone numbers, passwords, API keys, tokens, private certificates, or `.env` files.
- Commit only safe example configuration such as `.env.example` with placeholder values.
- Do not log passwords, tokens, uploaded document contents, or sensitive personal data.
- Validate uploaded file type, size, ownership, and access permissions.
- Do not assume a public URL is secure.
- Use established password and authentication practices; do not invent cryptography.
- Do not add a paid external service or require external credentials without approval.
- Never run destructive commands against production or shared environments.

---

## 14. Tests Before “Done”

Do not say:

- Done;
- Complete;
- Working;
- Fixed;
- Production-ready;

until the relevant behavior has been verified.

Verification may include, depending on the task:

- unit tests;
- integration/API tests;
- authorization and negative tests;
- Gherkin/BDD scenarios;
- formatter/linter;
- type checks;
- frontend/backend build;
- database migration checks;
- a reproducible manual demo flow.

Run the relevant checks available in the repository. Do not invent commands or claim a test passed unless you ran it and observed a successful result.

If verification could not be completed, state:

- what could not be tested;
- the exact command or setup that was attempted;
- the reason it could not run;
- what remains unverified.

Do not mark Jira Done until acceptance criteria, human review, CI, and the team's Definition of Done are satisfied.

---

## 15. Decisions Must Be Approved and Recorded

Coding agents do not independently approve product or major architecture decisions.

When a material decision is needed:

1. describe the ambiguity;
2. explain why it matters;
3. identify the affected behavior/components;
4. present options only when useful;
5. wait for the human decision.

After approval, record the decision in the appropriate existing project documentation, such as the Master Plan changelog, the relevant Jira issue, or an already-established decision record.

Do not invent a new decision-record system or create a new permanent documentation file unless the Product Owner approves it.

Do not use a decision log as permission to approve your own proposal.

---

## 16. Strict Git and Pull Request Rules

### Branches

- `main` is protected and reserved for approved release-ready work.
- `develop` is the shared integration branch.
- Start task branches from an up-to-date `develop`.
- Use one branch per Jira task or tightly related task group, not one branch per micro-edit.
- Naming examples:
  - `feature/GT-20-milestone-submission`
  - `fix/GT-21-late-flag`
  - `docs/GT-XX-task-spec`
  - `test/GT-24-supervisor-approval`

### Commits

Coding agents **are allowed to create organized commits** for assigned work after relevant acceptance criteria and checks pass.

Use Jira issue keys and concise Conventional Commit-style subjects:

```text
feat(GT-20): add milestone submission endpoint
fix(GT-21): correct late-submission boundary
test(GT-24): cover assigned-supervisor approval
docs(GT-XX): add developer task specification
```

- Commit meaningful, reviewable units; avoid one giant code dump and noisy commits for every tiny edit.
- Inspect `git status` and the staged diff before committing.
- Stage only files belonging to the assigned task.
- Run `git diff --check` and relevant tests/checks before push.
- Preserve the configured Git author identity.
- Never impersonate another developer, backdate commits, fabricate work, or rewrite published history without explicit approval.
- Never commit secrets, real personal data, unrelated changes, or generated artifacts that are not part of the task.

### Push and Pull Request

- After implementation and relevant checks pass, the agent may push its own task branch and open a PR targeting `develop`.
- If GitHub CLI/authentication is unavailable, do not claim a PR was created. Provide the branch name, suggested PR title, and complete PR description instead.
- The PR must identify the Jira issue, summarize behavior, list acceptance criteria, report tests/checks, include useful screenshots, and disclose known limitations.
- A human teammate must review the PR and CI before merge.
- Agents must not merge their own PRs, push directly to `main` or `develop`, force-push, bypass branch protection, or disable required checks.

Follow `docs/project/git-workflow.md` for the detailed workflow.

---

## 17. Context and Repository Discipline

Understand the Master Plan and repository structure at the beginning of a workstream.

For each task afterward:

- reread the relevant Master Plan sections;
- inspect the assigned task and directly related files;
- follow imports/callers only as needed;
- avoid repeatedly scanning the entire repository;
- avoid rereading large unrelated documents;
- avoid dumping large file contents when focused excerpts are sufficient.

Do not trade correctness for fewer tokens. The goal is to use relevant context efficiently without missing dependencies, security requirements, or existing behavior.

Do not assume a file, command, package, endpoint, or environment exists. Verify it in the repository.

---

## 18. Controlled Sub-Agent Delegation

Sub-agents may be used when they reduce context load or safely parallelize independent work.

Good delegation targets include:

- repository reconnaissance;
- implementation-pattern research;
- isolated code review;
- test review;
- bug isolation;
- comparing libraries or technical approaches;
- inspecting an independent subsystem.

Do not delegate product authority or major architecture approval.

A sub-agent must not independently:

- change product scope;
- approve a product decision;
- make a major architecture decision;
- reinterpret the Master Plan;
- modify files outside its assigned scope.

Do not spawn extra agents merely because parallelism is available. Keep delegation bounded and review the findings before acting on them.

A useful compact report is:

```text
Task researched:
Useful findings:
Recommended implementation approach:
Risks:
Relevant files:
```

---

## 19. Stop on Unexpected Damage or Conflict

If implementation causes or reveals unexpected damage, do not hide it with unrelated workarounds.

Examples:

- previously passing tests now fail;
- unrelated functionality breaks;
- unexpected files change;
- approved architecture assumptions conflict;
- an approved workflow becomes impossible;
- API/data contracts conflict between clients and backend;
- an existing user change would be overwritten.

First isolate the issue.

If the fix is clearly within the assigned task and does not change product/architecture decisions, fix it and verify it.

If resolving it requires a product decision, major architecture change, destructive operation, or substantial out-of-scope work, stop and ask the human developer.

Never reset, discard, overwrite, or stage unrelated user changes to make the working tree clean.

---

## 20. Required Task Reports

Before implementation, state briefly:

```text
Task:
Files expected to change:
Master Plan sections involved:
Out of scope:
```

After implementation, report:

```text
Task / Jira issue:
Task specification:
Implemented:
Files changed:
Tests / verification:
Branch / commits:
Pull Request:
Not implemented:
Deviations:
Known limitations:
Human action required:
Next step:
```

If there are no deviations, explicitly write `Deviations: None`.

Do not report a PR, commit, test, review, or merge that did not actually happen.

---

## Final Operating Principle

For every task, optimize for:

1. correctness;
2. compliance with the approved Master Plan;
3. minimal scope and minimal necessary changes;
4. reuse of proven work where useful;
5. protection of existing functionality and contracts;
6. clear verification;
7. secure handling of data;
8. clean coordination with other developers and agents;
9. low unnecessary complexity.

**Do not try to impress the team by adding architecture, files, abstractions, agents, dependencies, or features that were not requested.**

Implement the approved GradTrack task accurately, verify it, report what changed, and stop.
