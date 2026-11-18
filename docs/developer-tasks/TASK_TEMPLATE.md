# Developer Task Specification — [TASK TITLE]

> **Purpose:** Give one developer and their chosen coding agent a precise, bounded implementation contract. Complete the relevant sections before assigning the task. Delete instructional placeholders that do not apply; do not leave unresolved ambiguity for the coding agent to guess.

## 1. Task Information

| Field | Value |
|---|---|
| Jira Issue | `GT-XX` |
| Task Title | [Clear action + feature] |
| Epic | [Epic name / ID] |
| Assigned Developer | [Name] |
| Priority | [Critical / High / Medium / Low] |
| Type | [Feature / Bug Fix / UI / API / Test / Documentation / Refactor] |
| Target Client | [Backend / React Web / Flutter Mobile / Shared] |
| Depends On | [Issue IDs or None] |
| Status | [To Do / In Progress / In Review] |
| Specification Version | [1.0] |
| Prepared By / Date | [Name / YYYY-MM-DD] |

## 2. Objective

**What must be delivered?**

[Describe the exact user-visible or technical outcome in 2–5 sentences.]

**Why does it matter?**

[Explain the user value and how it supports the GradTrack product.]

## 3. Context and Existing Implementation

- **Relevant user/role:** [Student / Team Leader / Supervisor / Coordinator / System]
- **Current behavior:** [What the application does today; cite screens, endpoints, components, or files.]
- **Expected behavior:** [What should change after this task.]
- **Relevant files/components:** 
  - `[path/to/file]` — [why it matters]
  - `[path/to/file]` — [why it matters]
- **Related Jira stories / product decisions:** [IDs and short context]
- **Reference screenshots/designs/API docs:** [Links or attachments]

The coding agent must inspect the current implementation before editing. The paths above are starting points, not permission to overwrite unrelated code.

## 4. Scope

### In Scope

1. [Exact behavior/change #1]
2. [Exact behavior/change #2]
3. [Exact behavior/change #3]

### Out of Scope

1. [Related behavior that must not be implemented in this task]
2. [Unrelated refactor or redesign that must not be included]
3. [Future-priority feature deferred to another task]

### Files / Areas Allowed to Change

- `[path or directory]`
- `[path or directory]`

### Files / Areas to Avoid

- `[path or directory]`
- [Shared configuration, unrelated modules, or protected files]

If implementation genuinely requires changes outside the allowed area, the agent must explain why and ask before expanding scope.

## 5. Functional Requirements

Write requirements as observable behavior. Number them so they can be referenced during review.

### FR-1 — [Requirement name]

- Given: [starting condition]
- When: [user/system action]
- Then: [expected result]
- Validation: [input/permission/state validation]

### FR-2 — [Requirement name]

- Given: [starting condition]
- When: [user/system action]
- Then: [expected result]
- Validation: [input/permission/state validation]

### FR-3 — [Requirement name]

- Given: [starting condition]
- When: [user/system action]
- Then: [expected result]
- Validation: [input/permission/state validation]

[Add/remove requirement blocks as needed.]

## 6. UI/UX Requirements (if applicable)

- **Entry point/navigation:** [Where the user finds this feature]
- **Layout/content:** [Required sections, fields, controls, hierarchy]
- **Interactions:** [Click, submit, edit, cancel, filter, navigation behavior]
- **Loading state:** [What appears while data loads]
- **Empty state:** [What appears when there is no data]
- **Error state:** [Validation/network/server error behavior]
- **Success state:** [Confirmation and resulting UI]
- **Responsive behavior:** [Desktop/tablet/mobile expectations]
- **Accessibility:** [Keyboard, labels, contrast, focus, semantics]
- **Visual references:** [Link/image or explicit “follow existing design system”]

Do not invent a new design system or add decorative behavior that is not required.

## 7. API / Data Requirements (if applicable)

- **Endpoint(s):** [Method + path, or “not applicable”]
- **Request contract:** [Fields, types, required/optional, validation]
- **Response contract:** [Fields and status codes]
- **Authorization:** [Which role/team membership may perform this action]
- **Data changes:** [Entities/fields/relationships]
- **Migration required:** [Yes / No / To be assessed]
- **File handling:** [Allowed types, size limits, ownership/access rules]
- **Compatibility:** [Existing clients/routes that must remain compatible]

Do not invent an API or database contract when the architecture is undecided. Ask the task owner if a decision is required.

## 8. Acceptance Criteria

The task is accepted only when every applicable criterion below is satisfied.

- [ ] **AC-1:** [Specific, testable expected result]
- [ ] **AC-2:** [Specific, testable expected result]
- [ ] **AC-3:** [Specific, testable expected result]
- [ ] **AC-4:** [Specific, testable expected result]
- [ ] **AC-5:** [Relevant permission, validation, or error behavior]

Acceptance criteria must be observable and unambiguous. Avoid words such as “good,” “nice,” “fast,” or “user-friendly” unless a measurable definition is supplied.

## 9. Edge Cases and Failure Handling

| Case | Expected behavior |
|---|---|
| Empty/missing input | [Expected validation] |
| Invalid input | [Expected error] |
| Unauthorized user | [Expected denial; no data leakage] |
| Missing/deleted related record | [Expected behavior] |
| Duplicate/repeated action | [Expected behavior] |
| Network/server failure | [Expected UI/API response] |
| Boundary condition | [Exact expected behavior] |

Add feature-specific cases. Do not assume the table is exhaustive.

## 10. Testing Requirements

### Required Tests

- [ ] Unit tests for [behavior]
- [ ] Integration/API tests for [behavior]
- [ ] Permission/negative tests for [behavior]
- [ ] Gherkin scenario(s), if this changes a core user workflow
- [ ] Regression tests for affected existing behavior

### Commands to Run

```bash
# Replace with the actual commands already supported by this repository.
[format/lint command]
[type-check command, if configured]
[test command]
[build command, if relevant]
git diff --check
```

The agent must inspect the repository and use its actual scripts/commands. Do not invent a successful command or claim a check passed if it was not run.

## 11. Security, Privacy, and Course Constraints

- Use synthetic/test data only.
- Do not commit genuine student records, ID-card images, real phone numbers, passwords, tokens, or secrets.
- Enforce permissions on the backend for protected actions.
- Preserve team-level data isolation.
- [Add task-specific security/privacy rules.]
- [State any approved external service/credential dependency; otherwise do not introduce one.]

## 12. Implementation Constraints

- Follow root `agent.md` and the approved Master Plan.
- Follow existing repository patterns and dependencies.
- Keep the change limited to this task.
- Do not perform unrelated refactoring.
- Do not silently change product scope, data contracts, or shared configuration.
- If a necessary decision is missing, stop and ask the task owner.
- Do not merge the PR or push to `main`/`develop`.

## 13. Git Deliverables

- **Branch type:** [feature / fix / docs / test]
- **Suggested branch:** `[feature|fix|docs|test]/GT-XX-short-description`
- **Target PR branch:** `develop`
- **Commit format:** `type(GT-XX): short description`
- **Expected PR title:** `[GT-XX] Short task title`
- **Expected PR content:** summary, AC checklist, tests/checks, screenshots if useful, known limitations.

The coding agent may create logical commits, push the task branch, and open a PR after the acceptance criteria and relevant checks pass. It must not merge its own PR. A human teammate reviews the PR and CI before merge.

## 14. Definition of Done for This Task

- [ ] All applicable acceptance criteria pass.
- [ ] Relevant tests/checks have been run and results are reported.
- [ ] No unrelated changes or secrets are included.
- [ ] Documentation/API instructions are updated where needed.
- [ ] Logical commits exist on the task branch.
- [ ] Branch is pushed and PR targets `develop` (or the exact blocker is reported).
- [ ] Human review and CI are complete before Jira is moved to Done.
- [ ] Assigned developer understands and can explain the implementation.

## 15. Required Agent Completion Report

The developer must include this report in the handoff/PR description:

```text
Jira/task:
Task specification:
Branch:
Commits:
Pull Request:

Implemented:
- AC-1:
- AC-2:
- AC-3:

Files changed:
- ...

Tests/checks:
- Command:
  Result:

Decisions:
- ...

Known limitations / incomplete criteria:
- ...

Blockers / required human action:
- ...

Next step:
- ...
```

## 16. Notes and Approval

- **Open questions:** [List unresolved questions; do not hide them.]
- **Product Owner approval:** [Name / date / status]
- **Developer acknowledgement:** [Name / date]
- **Specification changes:** [Record changes and reasons]

---
*Use one file per bounded developer task. Keep the task small enough for one developer and one coding-agent implementation cycle, with reviewable acceptance criteria.*