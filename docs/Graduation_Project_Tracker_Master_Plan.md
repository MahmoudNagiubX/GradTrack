# GRADUATION PROJECT TRACKER
## Master Product Vision, Scope, Requirements & Agile Execution Plan

**Version:** 1.0 — Approved Product Scope Baseline  
**Date:** 11 November 2026  
**Course:** SET 312 — Agile Software Engineering (Group 1, Dr Cherry Aly)  
**Project:** Graduation Project Tracker  
**Status:** Product concept and complete feature scope agreed; implementation choices, final estimates, assignments, and acceptance criteria still to be finalized.  
**Primary reference:** `Agile SW_Project_Brief_Group1 (1)(3).pdf` (9 pages), along with the Agile lectures and labs in Google Drive.  
**Related assignment:** Week 4 User Stories, Acceptance Criteria & Planning Poker deliverables.

> **Purpose of this document**  
> This is the single master reference for the Graduation Project Tracker. It preserves the entire agreed product idea, all discussed features (including advanced features), the university-ID OCR workflow, user roles, graduation-project lifecycle, priorities, Agile course constraints, documentation and evidence strategy, reuse approach, and next steps. Supply this file to any new AI chat, developer, designer, or team member as project context. **Nothing listed as approved scope is silently dropped because it is challenging.** Priorities determine *when* to implement; they do not erase the long-term scope.

---

## 0. QUICK CONTEXT FOR A NEW CHAT OR CODING AGENT

- Build a **student-centered, end-to-end Graduation Project Management & Review Platform**, not merely a submission portal for supervisors.
- Student teams are the primary daily users; supervisors and programme coordinators receive their own dedicated views and permissions.
- The project must support the graduation-project lifecycle from team formation and topic proposal through requirements, design, implementation, testing, revisions, documentation, and final defense.
- **All four instructor-mandated MVP capabilities** are non-negotiable: assign each team to a supervisor; milestones with deadlines; submit file or link per milestone; assigned supervisor reviews with feedback and approve/return status.
- **Critical business rules:** late submissions are marked late; only the team's *assigned supervisor* may approve a milestone. Write unit tests and Gherkin scenarios for these rules.
- All discussed feature groups are in the master scope, organized into **Priority 1, 2, 3**. Priority 3 is still approved scope; it is not removed.
- **University ID-card scanning via OCR is a flagship differentiator.** It is an assisted enrollment/profile data-entry feature, not identity verification. Extract student name and student/university ID; prefill a confirmation form; allow manual completion of the remaining data. Validate accuracy using synthetic/redacted example cards for course work; do not store genuine student records.
- Offer manual account access, **Google Sign-In (OIDC)** as an option, and **email OTP verification** where useful. Support editable user profiles and photos, while preventing users from elevating their own system roles or falsifying verified identity attributes.
- Include team tasks, leader assignments, subtasks, comments, attachments/images, evidence of who completed each task, timeline, dashboards, reminders, versioned submissions, focus/Pomodoro, hardware inventory, meetings/docs, and AI-assisted project planning.
- Design quality matters: premium, polished, coherent, fast, smooth animations, strong UI/UX for student, supervisor, and coordinator views. Draw inspiration from Notion, TickTick, and the existing Smart Life Planner while creating an original product identity.
- Existing reference repo: <https://github.com/MahmoudNagiubX/Smart-Life-Planner> — Flutter, FastAPI, PostgreSQL. Reuse proven modules selectively after checking dependencies and licenses; **do not blindly copy the whole backend**.
- **Web vs Flutter is not yet finalized.** A responsive web app has been provisionally favored for supervisor/coordinator dashboards; Flutter remains possible, in which case produce an Android APK and test on the owner's Samsung A54. Do not claim either choice is final.
- Implementation tools: VS Code, PowerShell/terminal, Codex, Antigravity CLI. Tool use never replaces testing, review, security checks, or real team contributions.
- Course's working practices and required evidence are as important as the visible app: shared GitHub repo, shared Jira Scrum project, 5 total Sprints (Sprint 0–4), documentation each Sprint, real PRs/reviews/test contributions per member, CI, TDD, BDD, deployment/Docker, user feedback, and Week 12 live demo.
- The **urgent Week 4 assignment** lives in `docs/week4/` and includes story map with MVP line, Jira backlog screenshot, six top stories with acceptance criteria, estimation / INVEST / Planning Poker, and forecast.
- Important current context: the class is at Week 8 and intends to complete Sprint 0 and Sprint 1 work in Week 8, then follow the course milestones. Document actual work and dates honestly: **never fabricate backdated commits, meetings, comments, votes, reviews, team contributions, or history.**

---

## 1. PRODUCT IDENTITY AND VISION

### 1.1 Working name

**Graduation Project Tracker**. A stronger positioning / subtitle for presentation is **Graduation Project Management & Review Platform**. Final branding, logo, and visual identity remain open.

### 1.2 One-sentence vision

> A collaborative, student-first platform that manages the entire graduation project journey, helping teams organize daily work, coordinate shared resources, submit milestones, receive supervisor feedback, and demonstrate measurable progress from proposal to final defense.

### 1.3 Problem statement

- Student graduation teams spread work across chats, email, spreadsheets, task apps, and local folders.
- Team leads cannot reliably see task ownership, deadlines, contributions, blockers, and completion evidence.
- Supervisors follow multiple teams through fragmented emails; submissions, revisions, and feedback are difficult to track.
- Programme coordinators lack an accessible overview of projects, deadlines, delays, and evaluations.
- Graduation projects involving hardware additionally need material/components tracking, purchases and cost visibility.

### 1.4 Product strategy

The **student team is the primary beneficiary** and should receive the majority of daily-productivity value, rather than building a supervisor-only compliance portal. The product unifies student teamwork and formal academic oversight through shared project data, clear permissions, and evidence/history.

### 1.5 Success criteria

1. A team can create/maintain its project, distribute and finish tasks, share evidence, and follow its timeline.
2. Members can identify what is done, pending, blocked, overdue, and who owns or completed each task.
3. Students can submit milestones and understand feedback, late status, revisions, and approval outcomes.
4. The assigned supervisor can see project health and legitimately approve/return submissions.
5. The coordinator can inspect cohort progress at a glance.
6. The system is visually polished and reproducibly runs from the README.
7. The team can substantiate its Scrum process and engineering quality using authentic GitHub/Jira/test/review records.

---

## 2. USERS, ROLES AND PERMISSIONS

| Role | Primary goals | Typical capabilities |
|---|---|---|
| **Student / Team Member** | Work on graduation project | View team space, own/assigned tasks, updates, documents, files, focus sessions, milestones and supervisor feedback. |
| **Team Leader** | Coordinate the student team | Student capabilities plus assign/reassign tasks, coordinate workloads, request reviews, maintain team workboard and manage permitted team configuration. |
| **Assigned Supervisor** | Oversee assigned team(s) | Read team progress, review formal submissions, give feedback, approve or return milestones, inspect task and contribution history. |
| **Programme Coordinator** | Oversee programme/cohort | Programme-wide dashboard, deadline and lateness analytics, allowed oversight, grading administration and configuration as authorized. |

**Role model:** The brief defines three *stakeholder types*: student team, supervisor, programme coordinator. “Team leader” is a **permission/subrole within the student team**, not a replacement for an instructor-specified user type. A person may belong to a project/team and have project-scoped permissions; access must be enforced **server-side**, not merely by hiding buttons.

**Important rules:**
- A student cannot approve their own milestone or approve anyone else's team.
- A supervisor may approve only milestones belonging to teams assigned to that supervisor.
- A student can edit safe profile fields but cannot self-grant `supervisor`, `coordinator`, or `team_leader` permissions via a profile form.
- Team participation, permission changes, feedback actions, and approvals should be auditable.
- Supervisor/coordinator visibility is scoped to authorized projects and fields; no accidental cross-team leaks.

---

## 3. GRADUATION PROJECT LIFECYCLE — END TO END

These are the proposed workflow stages. They should be **configurable templates** rather than rigidly forced upon every graduation project.

1. **Team formation:** establish team, add members, designate leader, connect the assigned supervisor.
2. **Topic discovery:** brainstorm ideas, select a project direction, capture goals and constraints.
3. **Proposal and approval:** prepare and submit proposal, receive feedback, revise if requested.
4. **Research and requirements:** references, problem analysis, requirements and SRS milestones.
5. **Planning and design:** project plan, schedule, task breakdown, architecture and technical/mechanical designs.
6. **Development / implementation:** assign work, track code, hardware components, materials, purchases, meetings and files.
7. **Testing and integration:** record tests, defects, evidence, demo results and integration blockers.
8. **Iterative supervisor reviews:** formal milestone submissions, comments, version changes, approval/return/resubmit cycles.
9. **Final documentation:** reports, manuals, presentations, deliverables and source references.
10. **Final demonstration / defense:** deliver final build/demo, track readiness, submit final materials, record final evaluation where authorized.

**Central design principle:** Students should manage the *whole* journey in the same app. The formal milestone workflow coexists with a flexible daily task/project workspace.

---

## 4. INSTRUCTOR-MANDATED MVP (ALL FOUR REQUIRED)

### MVP-1 — Teams linked to a supervisor
- Create/view a student team, members, and designated leader.
- Associate a team with its assigned supervisor.
- Supervisor sees only assigned teams; coordinator sees authorized programme scope.
- Handle unassigned team states and invalid assignment attempts safely.

### MVP-2 — Milestones with deadlines
- Create/show project milestones (proposal, SRS, design, prototype/demo, etc.).
- Store deadline, description, state and ordering; show status and approaching deadlines.
- Allow legitimate supervisor/coordinator-configured milestone settings.

### MVP-3 — Submit a file or link per milestone
- Upload/attach file or provide external link, preserving ownership and submission timestamps.
- Show submission history, current version, late/on-time label, and link/file validation.
- Allow revised submissions where workflow permits; keep revision history.

### MVP-4 — Supervisor feedback and approve/return
- Assigned supervisor views pending submissions and provides written feedback.
- Supervisor approves or returns submission for changes; students read feedback and resubmit.
- Record reviewer, timestamp, decision and associated submission version.

### Non-negotiable business rules
1. **Lateness:** submission after its applicable deadline is flagged as late, using a consistent stored timezone/timestamp policy. No attempt to hide lateness on later resubmission.
2. **Approval authorization:** only the team's **currently assigned supervisor**, within authorized workflow rules, can approve that team's milestone.
3. Unit tests and explicit Gherkin normal/error scenarios must prove both rules.
4. Secure file permissions and cross-team isolation must also be tested.

**The original brief's sample stories** include a supervisor viewing all pending team submissions and a student reading SRS feedback before a deadline. Both must be reflected in the backlog.

---

## 5. COMPLETE AGREED FEATURE CATALOG

Every item in this section belongs to the **master product scope**. Some items will arrive in later priorities or increments, but none are silently dropped. Technical implementation details may be refined without losing the intended user outcome.

### 5.1 Account creation, authentication, and profile

**Account entry options**
- Manual registration and sign-in with secure credentials.
- **Google account sign-in** via industry-standard OpenID Connect as a convenient alternative.
- **Email OTP verification** for registration, verification, and/or recovery as appropriate; resend, expiration, and rate limits.
- Logout, account session handling, safe error messages, and a reasonable recovery path.

**University ID OCR registration option — flagship feature**
- User chooses **Scan university ID card** in registration/onboarding.
- Open camera or choose a local image; display a framing guide and retake option.
- Apply OCR to locate/read **full name** and **university/student ID number** from the pictured card.
- Prefill a review screen, clearly show confidence/uncertain fields, and let the user correct them.
- Ask for remaining data **manually**, e.g. faculty/department, programme, academic level/year, course/project context, email, password or Google-based account link.
- Academic level/faculty might be extracted **only if reliably present** and validated on the card; **never infer or claim verified graduation eligibility from OCR alone.**
- ID image should be transient by default and not persist or be uploaded without a separately justified need and explicit action.
- Do not treat recognized text as proof that the person owns the university identity; real verification requires trusted university records or another institution-approved mechanism.
- Prefer an OCR module with robust **Arabic and English** support. Candidate technologies to evaluate include PaddleOCR, Google ML Kit and other on-device/server approaches. Existing Egyptian national-ID OCR examples may inspire preprocessing but are **not automatically trained for university ID layouts**.
- Define measurable OCR evaluation: exact match on student number, normalized name match, extraction failure rate, scan time, and false-positive handling; select solution only after test results.
- Make OCR optional: students always have a manual registration fallback.

**Profile / identity management**
- User profile with name, avatar/profile photo, displayed student/university ID, faculty, department/specialization, level, team, and project role.
- Editable permitted personal/profile fields, profile picture upload/change/delete, and optional biography/contact preferences.
- Clearly separate **editable display name** from verified/administratively controlled identity fields.
- Show team leader, member, supervisor, or coordinator context; only authorized administrators/team workflows can alter privileged roles.
- Optional preferences include theme, notification preferences, language, and basic accessibility choices.

### 5.2 Team workspace and task management (student-first)

- Team/project home dashboard: overview, next deadlines, progress, recently updated tasks, member activity.
- Team creation, membership, designated team leader and supervisor association.
- Leader creates tasks, assigns members, sets priority, due dates, status, estimates and descriptions.
- Members create or update tasks as permissions allow, mark progress, leave status updates and report blockers.
- To-do list, Kanban board, and calendar/timeline views.
- Subtasks, task checklists, categories/tags and task dependencies where beneficial.
- Comments/discussion on tasks, @mention-style notification concept, timestamps and edit history.
- Attach task files, photos, images and relevant links, including hardware progress or design screenshots.
- Clearly track **who created, owns, changed, and completed** each task and when.
- Supervisor read-only oversight of team tasks by default; any direct task-management controls require explicit permission design.
- Weekly workload and progress visibility; simple filters by assignee, status, project phase and deadline.
- Daily work should feel organized like quality productivity apps, taking inspiration from **Notion** and **TickTick** without copying their interface or proprietary code.

### 5.3 Timeline, milestones, and project planning

- **Interactive timeline** / Gantt-like visualization spanning graduation-project lifecycle stages.
- Milestone map and task timeline with due dates, planned/actual progress and visual status.
- Task/milestone dependency links and timeline conflict/overdue indicators where achievable.
- Calendar view for key events, reviews, submissions, and internal team tasks.
- Visual project-progress indicators and estimated completion/at-risk warnings.
- Configurable phase templates (proposal, SRS, design, prototype, implementation, testing, report, defense).

### 5.4 Submission and feedback management

- File or URL submission to a milestone.
- Student/team-facing submission status: draft, submitted, pending review, returned, resubmitted, approved; late flag as separate attribute.
- Clear feedback threads, review notes and revision requests.
- **Version history:** preserve multiple submission versions and trace which feedback/approval applies to which version.
- Supervisor review inbox, team filtering and pending submissions.
- Coordinator-appropriate oversight without circumventing supervisor approval rule.
- Audit trail of approvals, returns, timestamps and actor IDs.

### 5.5 Collaboration and shared knowledge

- Shared project document/file space, including SRS, proposals, architecture, designs, research references and handover materials.
- Meeting notes and action items, with owners, due dates and references back to tasks.
- Team activity feed displaying legitimate work updates and recent completions.
- Shared progress log and blockers journal.
- Lightweight decision log: what changed, why, who agreed and when.
- Versioned or traceable changes where feasible, especially for formal submissions.

### 5.6 Analytics dashboards

**Student / leader dashboard:**
- Project completion, finished vs unfinished tasks, late/blocked tasks, tasks per member, focus activity and approaching milestones.
- Team contribution indicators **based on actual logged actions**, not invented productivity scores.

**Supervisor dashboard:**
- All assigned teams, progress, submission queue, review times, at-risk deadlines and project health.

**Programme coordinator dashboard:**
- Authorized programme/cohort-wide progress, completion trends, late/at-risk projects, review/approval counts and grading overview if enabled.

### 5.7 Smart reminders and notifications

- Deadline approaching and overdue alerts for formal milestones and team tasks.
- New assignment, comment, mention, supervisor feedback, return, approval and upcoming review alerts.
- Notification center with unread/read states and preferences.
- Delivery channels selected after stack decision (in-app mandatory concept; push/email optional by feasibility).
- Prevent duplicate or stale reminders after tasks/deadlines are changed.

### 5.8 Focus and productivity tools

- **Pomodoro-style focus timer** linked to a selected task.
- Start/pause/finish focus sessions; track duration and completed sessions.
- Individual focus statistics and optional personal productivity trends.
- Link sessions to genuine task work without equating time spent with guaranteed output.
- Simple daily or weekly goals and task recommendations if useful.

### 5.9 Hardware/component inventory and expenses

- Support software-only **and** hardware-involved graduation projects.
- Component/material list with item name, quantity, status (planned, ordered, received, used), supplier and expected/actual cost.
- Attach product photos, receipts/test images and external links using test/example data.
- Track procurement tasks and hardware assembly/testing progress.
- Team budget/expense summary without real payment processing.
- Hardware inventory is an optional product module, not a universal requirement for every project.

### 5.10 AI-assisted graduation-project work

- Suggest task breakdowns and subtasks from a milestone or project goal.
- Help plan next actions based on due dates, assigned work and dependencies.
- Summarize meeting notes, blockers or task discussions with explicit user review.
- Draft project progress summaries or weekly status reports for students and supervisors.
- Offer deadline/risk insights and help prepare presentations/documentation.
- AI output remains **assistive**: it does not approve milestones, invent contributions, autonomously send submissions, or overwrite source-of-truth data.
- Provide explainable deterministic rules or non-AI fallbacks where possible; API cost/privacy and reliability must be evaluated before implementing external AI services.

### 5.11 Grading and programme administration

- Authorized grading sheet/rubric by milestone or evaluation criterion.
- Optional final evaluation aggregation and coordinator reporting.
- View/control grade visibility according to role; avoid exposing one team's evaluation to another team.
- Keep grading separate from daily task tracking and preserve auditability.

---

## 6. THREE APPROVED DELIVERY PRIORITIES

**Scope contract:** All three levels are included in the agreed overall idea. Do not reinterpret lower-priority items as canceled. The point of prioritization is to protect a working, tested course submission while continuing toward the larger vision.

### PRIORITY 1 — Functional foundation and daily team value

1. All four required course MVP capabilities and their business rules.
2. Basic account system, secure login/logout, accounts and role-based access.
3. User profile, profile edits and avatar basics; safe role display and authorized edits.
4. Student team workspace: team/member management and team leader.
5. Collaborative task management: to-do, assignments, status, deadlines, subtasks, comments, task files/images, completion activity.
6. Working student and supervisor views of tasks, deadlines and formal milestone workflow.
7. Essential team/project dashboard and responsive, polished core design.
8. Tests and end-to-end vertical flows rather than disconnected frontend-only screens.

### PRIORITY 2 — Polished collaboration, planning, visibility and access options

1. **Interactive timeline** and richer milestone/task dependencies.
2. **Analytics dashboards** for student/leader, supervisor and coordinator.
3. **Smart reminders and notification center.**
4. Submission **version history**, detailed activity trail and reviewer feedback threads.
5. Shared workspace documents, meeting notes, decision/activity logs and collaboration enhancements.
6. **Google Sign-In** and **email OTP** where appropriate; profile/identity polish.
7. Stronger calendar views, advanced progress reporting and improved animations/UX.

### PRIORITY 3 — Flagship innovation and advanced tools

1. **University ID OCR scanning, extraction, review and manual fallback** (a high-visibility differentiation feature).
2. **Focus/Pomodoro sessions** and productivity statistics.
3. **Hardware/component inventory, costs and procurement workflows.**
4. **AI-assisted** planning, task breakdowns, summaries and project guidance.
5. **Grading sheet** and advanced coordinator reports.
6. Extra refinements guided by real user feedback.

**Special sequencing decision for OCR:** Although full OCR integration is Priority 3, perform a **small early feasibility spike** while planning/starting work: test supported OCR engines against **synthetic/redacted university-ID-like images** so the most important differentiator does not fail at the end. Log test results and decision; do not make OCR a blocker for the required course MVP.

---

## 7. UX / UI DESIGN DIRECTION

### 7.1 Experience target

- Premium, modern, coherent design that feels like a production-ready software product.
- Particularly strong visual craftsmanship: clear layouts, refined typography, spacing, card systems, icons, status badges, dark/light support where feasible, smooth but restrained transitions.
- Smooth navigation and responsive performance with sensible loading, empty, error and success states.
- Workflows must prioritize *real user value* over animation that hides information or slows task completion.

### 7.2 Main screens / navigation candidates

**Student:** Welcome / Sign in / Register / Scan Card / Verify OTP / Profile Setup / My Team / Home Dashboard / My Tasks / Team Board / Task Details / Timeline / Milestones / Submission / Feedback / Project Files / Meetings / Focus Timer / Inventory / Notifications / Profile Settings / AI Helper.

**Supervisor:** Assigned Teams / Supervisor Dashboard / Team Overview / Pending Reviews / Submission Details / Feedback & Approval / Activity & Task Progress / Notifications / Profile.

**Coordinator:** Programme Dashboard / Team List / Progress Analytics / Overdue Projects / Milestone Overview / Evaluation / Reports / Profile.

### 7.3 Inspiration and design reuse

- **Notion:** modular project knowledge, structured pages, linked documents, databases and collaborative organization.
- **TickTick:** excellent daily task clarity, recurrence/reminder patterns, calendar, focus/Pomodoro and lightweight interaction design.
- **Smart Life Planner:** existing design tokens, cards, dashboard motifs, task and timeline layouts, navigation patterns, reminder/focus UI; reuse selectively and adapt to the new brand/user roles.

All inspiration is directional; create original screens, branding, interaction flows and architecture.

### 7.4 Web versus Flutter — not decided

**Responsive web app:** especially suitable for supervisors, coordinators, dashboards, desktop file reviews and easy browser-based demos. Current provisional preference.

**Flutter app:** possible for attractive mobile-first UI and device demo; must generate an installable Android APK, test on the user's Samsung A54 and ensure API hosting/device access works on the real phone.

**Selection criteria:** team skill/capacity; actual reuse from Smart Life Planner; interface needs of all roles; deployment simplicity; automated testability; time to a polished, reliable demo. **Do not prematurely lock the frontend.**

---

## 8. TECHNOLOGY, EXISTING CODE, AND IMPLEMENTATION ENVIRONMENT

### 8.1 Existing Smart Life Planner repository

<https://github.com/MahmoudNagiubX/Smart-Life-Planner>

Previously inspected: Flutter/Dart frontend, FastAPI/Python backend, PostgreSQL and Alembic, JWT/security, task/project models and APIs, project-timeline logic, reminders, focus flows, test modules, design-system documentation and reference screens.

**Candidate selective reuse:**
- Auth/security primitives and user/account patterns, after audit and adaptation.
- FastAPI application structure, database access, migrations, schemas/repositories.
- Task, project and deadline infrastructure as a starting point (not a drop-in graduation team model).
- Timeline logic and related Flutter/visualization ideas.
- Reminder/focus building blocks and design tokens.
- Certain general UI states/components and tests, subject to app-specific compatibility.

**Requires new or significantly altered design:**
- Multiple project users and team-scoped membership, roles and permissions.
- Supervisor-to-team assignment and restricted approval authorization.
- Milestone submission files/links, versioning and review workflow.
- Formal academic programme/coordinator dashboards.
- University ID-card OCR and the onboarding review flow.
- Hardware inventory and grading modules.

**Do not:** import irrelevant spiritual, prayer or AI modules wholesale; copy secrets, `.env` files or developer logs; transfer old sample student data; preserve old project branding; assume code works without tests.

### 8.2 Working environment and AI tools

- **VS Code** is the editor; **PowerShell/terminal** is the command-line environment.
- **Codex** and **Antigravity CLI** are coding assistants; they may scaffold, edit and propose tests/docs.
- Human team members own the decisions, reviews, corrections and actual contributions.
- Each substantial change ties to a real Jira issue and goes through a branch, commit, pull request, review and CI when the workflow is established.

### 8.3 Repository structure (mandatory core)

The instructor explicitly requires:

```text
Graduation-Project-Tracker/
├── README.md                     # install, run, test, demonstrate
├── src/                          # application code; may contain frontend/ and backend/
├── tests/                        # unit tests / TDD evidence
├── features/                     # Gherkin .feature files + step definitions
├── .github/
│   └── workflows/
│       └── ci.yml                # tests + linter on PRs and main
└── docs/
    ├── project/
    │   ├── vision.md
    │   ├── definition-of-done.md
    │   ├── sprint-0-review.md
    │   ├── retro-0.md
    │   ├── sprint-1-review.md
    │   ├── retro-1.md
    │   ├── sprint-2-review.md
    │   ├── retro-2.md
    │   ├── sprint-3-review.md
    │   ├── retro-3.md
    │   ├── sprint-4-review.md
    │   ├── retro-4.md
    │   └── feedback.md
    └── week4/
        ├── story-map.jpg
        ├── backlog.png
        ├── stories.md
        ├── estimation.md
        └── forecast.md
```

Additional subdirectories and documentation are welcome, but **do not replace or omit** required paths. After stack decision, fit source code under `src/` cleanly; support tests and Gherkin in the indicated locations (internal package tests may coexist where tooling requires them).

---

## 9. COURSE REQUIREMENTS AND CONSTRAINTS (SOURCE-OF-TRUTH)

### 9.1 Team and basic ground rules

- Course team: **4–5 students**; project is worth **15 marks**.
- One Product Owner (PO), one Scrum Master (SM), all members are Developers, including PO and SM.
- **Rotate PO and SM once at the start of Sprint 3** so different people hold each role.
- In a five-person team, the fifth member additionally owns CI/CD/test quality or a stretch epic as agreed, while balancing work fairly.
- Use **test data only**: no real student records, real phone numbers or real payments in the project.
- One **shared GitHub repo** and one **shared Jira project**; add instructor and TA with appropriate access.
- Real commit history is evidence; no last-minute single upload commit.
- Every member must have **actual merged PRs and tests under their name**. A member with no merged code can lose Engineering Quality marks.
- Each member speaks at the final demo and submits/participates in peer evaluation as required.
- Project choice needs approval; two independent teams on one idea must not share code with each other. Reusing the owner's existing independent repository must be reviewed for authorship/license and instructor academic-integrity expectations before incorporation.

### 9.2 Marking rubric

| Criterion | Marks | Evidence |
|---|---:|---|
| Working product (MVP) | **4** | Four required epics, business rules, demo, README and meaningful UI/errors |
| Agile process | **4** | >=15 INVEST stories with AC and estimates, Jira Sprints/goals, reviews/retros, burndown/velocity, role rotation |
| Engineering quality | **4** | TDD unit tests, >=5 passing Gherkin scenarios, green CI, reviewed PRs, linter, deployed or Dockerized |
| User feedback & adaptation | **2** | >=3 real users, summarized feedback and demonstrable backlog/product adaptation |
| Demo & teamwork | **1** | 10-minute demo, all members speak, handle Q&A |
| **Total** | **15** | Course brief does not guarantee separate bonus marks merely for extra features |

**Strategy:** Deliver real MVP + quality + real process evidence before spending all available time on stretch features. A beautiful screen cannot compensate for missing CI, a fake Agile history, or missing business-rule tests.

### 9.3 Course sprint timeline

| Week | Sprint | Mandatory deliverables |
|---|---|---|
| **7** | **Sprint 0 — Setup** | Team registration/approval, one-paragraph vision, GitHub repo, Jira project, >=15 prioritized pointed stories, Definition of Done |
| **8** | **Sprint 1 — Walking Skeleton** | Thin end-to-end working increment: about one story per member; GitHub Actions CI runs tests and linter on PRs |
| **9** | **Sprint 2 — Deliver** | Second increment; deployed to free host **or** runnable through Docker; >=5 passing Gherkin scenarios |
| **10** | **Sprint 3 — MVP & Feedback** | All four MVP epics complete; feedback from >=3 real users, `feedback.md`, backlog reordered; rotate PO/SM |
| **11** | **Sprint 4 — Improve** | Fixes/changes from feedback, at least one stretch story (brief describes it as optional), final retro, release tag `v1.0` |
| **12** | **Capstone Demo** | 10-minute live demo, then 5-minute Q&A, all members speak, peer evaluation |

The team is currently catching up in Week 8 and plans to address Sprint 0 and Sprint 1 work during that period. **Use authentic creation/completion dates; if a milestone happens late, record the schedule deviation and corrective action. Do not falsely backdate Jira history or commits.**

### 9.4 Every Sprint ritual

- **Planning:** decide Sprint Goal, realistic capacity and selected Jira stories; decompose into short tasks.
- **Stand-ups:** at least **three short team check-ins per week**, documented concisely by the Scrum Master (including WhatsApp/Discord when appropriate).
- **Review:** demonstrate the actual working increment to the TA/stakeholder; PO accepts/rejects individual stories based on acceptance criteria.
- **Retrospective:** Start / Stop / Continue; choose a concrete improvement action for the next Sprint.
- **Evidence:** time-stamped decisions, board changes, actual tests, branch/PR links and review notes. Do not invent meetings or contributions.
- Track Sprint Goal, backlog scope, completed points, unfinished items, blockers and velocity/burndown transparently.

### 9.5 Definition of Done — proposed baseline for agreement

A story reaches `Done` only when relevant conditions hold:
- Story's own acceptance criteria pass.
- Code meets agreed style; linter/static analysis green.
- Appropriate unit and/or integration tests pass; business-rule changes include test evidence.
- Relevant BDD scenarios pass when applicable.
- A teammate actually reviewed the PR, changes were addressed, branch merged and CI green.
- No unresolved high-severity security/privacy defects.
- README/docs/API or usage instructions updated when needed.
- Jira issue reflects real work; screenshots/links attached where useful.
- Working increment can be demonstrated with test data.

This is a **proposed team DoD**; the team must review and adopt its final version in `docs/project/definition-of-done.md`.

---

## 10. URGENT WEEK 4 ASSIGNMENT — COMPLETE CHECKLIST

**Original assignment:** Submit the team's `docs/week4/` folder containing a photo of the story map with MVP line; a Jira backlog screenshot with >=12 stories and points; and `stories.md`, `estimation.md`, `forecast.md`. Each member submits as instructed through the LMS. The lab document states a deadline is set separately by the instructor; do not invent one.

| File | Required content |
|---|---|
| `docs/week4/story-map.jpg` | Actual story map photo; 3–5 epics/backbone left-to-right; stories above/below a clearly drawn **MVP line** |
| `docs/week4/backlog.png` | **Actual** Jira backlog screenshot showing epics and >=12 prioritized Stories with point values (create >=15 to also satisfy project brief) |
| `docs/week4/stories.md` | Top **6** backlog stories, each with >=2 **Given–When–Then** scenarios: one success and one error/edge case; consistent with Jira |
| `docs/week4/estimation.md` | INVEST check table and real Planning Poker records: votes/rounds/final estimates/key discussions; split oversized stories |
| `docs/week4/forecast.md` | Total backlog points, proposed **baseline** velocity (not falsely presented as measured), forecast Sprints, remaining Sprints, MVP-line capacity, 3–4 sentence reflection |

Additional Lab 4 notes:
- Each Story: `As a [specific role], I want [goal], so that [benefit].`
- Story should satisfy INVEST: Independent, Negotiable, Valuable, Estimable, Small, Testable.
- Use SPIDR (Spike / Paths / Interfaces / Data / Rules) to split oversize work into useful **vertical** slices, not separate front-end-only/back-end-only stories.
- Story points are relative **effort + complexity + uncertainty**; Planning Poker cards include 0/1/2/3/5/8/13/20/40/100/?; if 13+ points, split.
- In the lab, PO reads the story and **does not vote**; Developers choose secretly and reveal together, discuss differences, then vote again.
- A baseline velocity is a **forecast assumption before Sprint 1**, not an observed velocity. Use the team's capacity, then update the forecast with real Done points when available.
- The Week 4 assignment can be submitted after **minimum setup + stories/epics/estimates + Jira**; app coding need not be complete first.

---

## 11. HIGH-LEVEL BACKLOG / EPICS (FOR FUTURE STORY MAPPING)

This is an illustrative decomposition, **not** a claim that these Jira items already exist or have team-approved story points. Keep all four required MVP epic groups prominent; group enhancements under appropriate feature areas.

**EPIC A — Identity & Team Setup**
- Create account and manual sign in; profile; avatar; join/create team; designate leader; connect assigned supervisor; role-safe access.
- Google sign-in; email OTP; university ID OCR-assisted onboarding.

**EPIC B — Project Milestones & Submissions [MANDATORY MVP]**
- Add/view milestone and deadline; submit URL/file; view pending/late status; resubmit/version history; view status and past revisions.

**EPIC C — Supervisor Review & Approval [MANDATORY MVP]**
- Assigned team dashboard; pending submission inbox; comments; return for corrections; approve submission; block wrong supervisor approval.

**EPIC D — Team Task Collaboration**
- Team leader assigns task; member updates task; subtasks; comments; photos/attachments; board/list; activity log; blockers and contributions.

**EPIC E — Scheduling, Timeline & Reminders**
- Interactive project timeline and dependencies; calendar; deadlines; in-app reminders; notification center; alert rules.

**EPIC F — Analytics & Coordinator Oversight**
- Team progress dashboard; supervisor view; coordinator cohort metrics; late/at-risk reports; grading.

**EPIC G — Shared Knowledge and Productivity**
- Shared project files and meeting notes; focus timer; session records; decisions and progress summaries.

**EPIC H — Hardware and AI Assistance**
- Inventory/cost tracking; procurement; AI-generated task suggestions, meeting summaries and project planning help.

**Interpretation of the instructor's four MVP features:** Although implementation epics might be grouped differently on Jira, the four mandatory behaviors (team-supervisor link, deadlines, submission, approval/return) must be explicitly traceable and visible **above the MVP line**. For the Week 4 story map, a 4–5-epic backbone is cleaner than treating every enhancement as a separate mega-epic.

---

## 12. IMPORTANT USER JOURNEYS

### Journey A — Student enters the platform

1. Open polished welcome/login page.
2. Choose manual account, Google Sign-In, or optional **Scan University ID** during registration.
3. If scanning, camera reads name and university ID; student confirms/corrects; manually completes remaining profile details.
4. Complete permitted email OTP/verification flow if enabled.
5. Join or establish team with authorized process; see team dashboard and graduation-project stages.

### Journey B — Leader coordinates work

1. See project timeline and team workload.
2. Create task with due date/priority, link it to project milestone, assign a teammate.
3. Member receives notification, starts work, optionally logs Pomodoro sessions, uploads image or file, adds updates.
4. Member finishes task; history records actor and timestamp; dashboard updates.
5. Leader identifies blockers and reallocates work when necessary.

### Journey C — Team submits and supervisor reviews

1. Team opens an upcoming SRS/design/proposal milestone with deadline.
2. Student submits a file/link; system stores submission time and late status.
3. Assigned supervisor sees submission in review inbox, comments and returns for revision **or** approves.
4. Student reads feedback, updates the work and submits a new version while past feedback remains visible.
5. Coordinator sees appropriate aggregate progress without bypassing supervisor authorization.

### Journey D — Project reaches final defense

1. Team tracks final milestones, hardware/resources, testing, final report and presentation tasks.
2. Dashboard indicates completion/readiness, outstanding issues and reviews.
3. Team uploads final deliverables, receives formal review and demonstrates progress evidence.
4. Authorized staff records grading/reporting information as allowed.

---

## 13. DATA MODEL — FIRST-PASS DOMAIN ENTITIES

These are **conceptual**, not final table definitions:

- `User`, `AuthIdentity`, `VerificationChallenge`, `UserProfile`, `ProfilePhoto`
- `Programme`, `GraduationProject`, `Team`, `TeamMembership`, `TeamRole`, `SupervisorAssignment`
- `ProjectPhase`, `Milestone`, `MilestoneDeadline`, `MilestoneSubmission`, `SubmissionVersion`, `SupervisorReview`
- `Task`, `Subtask`, `TaskAssignment`, `TaskComment`, `TaskAttachment`, `TaskActivity`, `TaskDependency`
- `ProjectFile`, `MeetingNote`, `DecisionRecord`, `ProgressUpdate`
- `Notification`, `ReminderPreference`, `FocusSession`
- `InventoryItem`, `ProcurementEntry`, `CostRecord`
- `EvaluationRubric`, `EvaluationEntry`
- `AuditEvent`, `FeedbackRecord`

Important relationships: Team -> one assigned supervisor context (at a time); Project -> milestones and tasks; Milestone -> submission versions -> review actions; Task -> assignee(s)/attachments/history; users have system roles **and** project/team membership roles. Do not reuse `Smart Life Planner`'s single-owner task model unchanged for a multi-member project.

---

## 14. QUALITY, TESTING, PRIVACY AND DEMO SAFETY

### 14.1 Tests

- **TDD:** late submission boundaries (on time, just after, resubmission), allowed/forbidden approval, cross-team isolation, rejected file/URL and invalid states.
- **BDD:** >=5 automated, passing Gherkin scenarios across the core real-world workflows; include happy paths and permission/deadline edge cases.
- **CI:** linter + unit/integration/BDD checks appropriate to stack on each PR; green on `main`.
- **CD / delivery:** deploy to free host or provide an actually runnable Docker arrangement by the required Sprint. README documents reproducible setup.
- **UX:** test camera permission denied, low-confidence OCR, failed Google sign-in, expired OTP, empty dashboards, absent files, unavailable network, upload size/error and accessibility.

### 14.2 ID/OCR and course restriction — mandatory distinction

- The course brief explicitly says: **“Use test data only: no real student records, no real payment processing, no real phone numbers.”**
- The project owner proposed evaluating OCR using their real university ID. For course compliance, **the official repository, shared drives, CI, screenshots, demo, fixtures and user feedback sessions must use synthetic/test IDs and invented personal details**.
- If the owner privately experiments with their personally owned card for OCR research, do so **outside the graded project data pipeline** (ideally locally/offline), never commit, upload, distribute, log or retain the real photo or extracted name/ID; remove any incidental files/logs. That private experiment is not a replacement for the synthetic official tests.
- OCR extracts text; it is **not** institutional identity verification or an automatic proof of academic level/eligibility.
- Use rate limits/short expiration on OTP. No plaintext passwords or secrets in source control. Validate file types/sizes and storage access. Maintain audit data without dumping sensitive content into logs.
- Use a realistic synthetic project/team dataset for demonstrations; obtain >=3 real users' usability **feedback** without storing their genuine student records.

### 14.3 Evidence integrity

- **Commits, Jira events, PR comments, code reviews, test logs and screenshots are evidence, not decoration.**
- Every member should have **genuine** tasks assigned to their capabilities: UI component, simple validation, tests, small API, documentation, test automation, etc. Review their actual changes.
- Don't attribute the owner's AI-assisted implementation to another person; don't manufacture commits or paste fake Slack/WhatsApp discussions.
- Keep work log/provenance of reused pre-existing code (from the owner's Smart Life Planner), clearly distinguish existing reused modules from new course-sprint work; ask TA about reuse policy when uncertain.

---

## 15. TEAM OPERATING MODEL AND DOCUMENTATION STRATEGY

### 15.1 Roles

- User/project organizer intends to serve as **PO + Developer**, not as a nontechnical PO.
- Other members contribute real deliverables, even if less experienced. Provide bounded, approachable pieces of work and peer help instead of evidence fabrication.
- SM manages ceremonies, impediments, truthful Jira board and retrospective notes.
- Rotate PO and SM in Sprint 3, as required; original owner can continue developing and collaborating on vision and scope.

### 15.2 Workflow convention (proposal)

`Jira Story -> feature branch -> incremental commits -> PR -> actual peer review comments -> CI passing -> merge -> Jira Done -> Sprint review note`

Use Jira issue keys in branches/commits/PR descriptions when possible. Do not create a one-shot code dump. Record the why behind decisions and story scope change.

### 15.3 Per-sprint documentation checklist

For **every Sprint 0–4**, keep actual dated content:

- Sprint number, dates, goal, capacity assumptions, selected Jira story IDs and estimated points.
- Team/roles and real responsibilities, planning decisions, tasks and dependencies.
- Stand-up/check-in notes (>=3 weekly) and legitimate blockers.
- Links to GitHub branches, PRs, reviews, merge commits, relevant code and tests.
- CI runs, linter/unit/BDD result, deploy/Docker evidence and screenshots if relevant.
- Working increment demo/review, stakeholder comments, PO acceptance/rejection.
- Retrospective: Start / Stop / Continue + one next-Sprint action and follow-up.
- Scope changes, carryover stories, velocity/burndown data; actual vs planned differences.

### 15.4 Final documentation assembly

The final Agile documentation report should assemble **authentic per-Sprint artifacts**, rather than reconstructing invented process at the end. Cover vision, stakeholder roles, user story map and MVP line, INVEST/acceptance criteria, estimation and forecast, sprint planning/results, Jira evidence, Git/PR evidence, TDD/BDD, CI/CD, feedback, product decisions and retrospectives. Add citations/links to source evidence.

---

## 16. DEMO AND MARKS STRATEGY

**Week 12 demo — 10 minutes + 5-minute Q&A:**

1. **0–1 min:** problem, stakeholders, product vision (PO).
2. **1–6 min:** live **realistic user journey**, not slides for app features: student task + milestone submit -> supervisor review and feedback -> coordinator/team overview.
3. **6–8 min:** show actual CI run, unit tests and one passing Gherkin scenario.
4. **8–10 min:** show Jira board, velocity/burndown, specific user-feedback adaptation, one real retro lesson (SM).
5. **10–15 min:** instructor/TA questions; every team member able to explain actual contributions.

**Visual wow moments (only after core compliance):** clear team dashboard, smoothly animated interactive timeline, supervisor approval workflow, notifications, a trustworthy OCR scan-and-confirm flow if ready, beautiful student task boards, responsive coordinator analytics.

**Bonus-mark realism:** The project brief lists a 15-mark rubric but does **not** promise a separate numerical bonus for more features. Enhancements are intended to increase quality and presentation distinction **without threatening mandatory marks**.

---

## 17. MAJOR RISKS AND GUARDRAILS

| Risk | Guardrail |
|---|---|
| Too many features for short course schedule | Maintain 3 priorities, keep all agreed scope documented, protect finished MVP, TDD/BDD/CI and demo |
| Reusing old backend without adapting ownership | Audit user/team authorization, migrate selectively, write tests |
| OCR inaccurate on university cards | Early synthetic-card feasibility spike, manual correction and fallback, measurable accuracy benchmarks |
| Real university ID leaked | No real student records or authentic ID pictures in graded repo, uploads, CI, screenshots or demo |
| More animations than functionality | Define performance, accessibility and error-state standards alongside design |
| AI writes everything, other members have no real code | Assign achievable genuine member work, reviewed PRs and tests; do not forge evidence |
| Unreliable manual Google/OTP flows | Support deterministic local demo/test path, handle setup failures transparently, use rate limits |
| Sprint history manufactured retroactively | Record actual dates and deviations; make honest catch-up planning and retrospectives |
| Web vs Flutter choice delayed too long | Timebox feasibility comparison and choose before Sprint 1 architecture is locked |
| Final report loses details | Log per-Sprint evidence immediately with links to actual sources |

---

## 18. STATUS: FIXED DECISIONS VS OPEN DECISIONS

### Already agreed / in scope

- Product identity and student-first orientation; complete graduation lifecycle.
- All four mandated MVP behaviors and business rules.
- Three user stakeholder types, plus team leader student subrole.
- All feature modules catalogued in Section 5.
- Three implementation priorities described in Section 6.
- Strong design/animation/smoothness and premium UX direction.
- OCR university card scanning as flagship; extract name and student ID; manual review and completion.
- Manual login + optional Google Sign-In + OTP; editable profile and avatar.
- Selective reuse of Smart Life Planner as a reference and possible source modules.
- Codex + Antigravity CLI in VS Code/PowerShell.
- GitHub/Jira + documented honest Agile development and Week 4 assignment.

### Not yet finalized (do not silently invent answers)

1. Frontend platform: responsive Web, Flutter Android or combination.
2. Final UI branding, visual palette, logo and design system.
3. Exact feature cut per Sprint and accepted baseline velocity.
4. Final database and file/object storage design; cloud/demo hosting.
5. Exact university card layout, scanner engine and benchmark accuracy.
6. How university IDs are institutionally verified (OCR alone cannot verify).
7. Exact Google/OIDC provider configuration and OTP delivery policy.
8. Final team membership, identities, GitHub/Jira URLs, role rotation assignments and TA approval status.
9. Final Jira story IDs, estimates, Definition of Done and specific due dates for class assignment.
10. Precise AI provider/API usage, permissions, data retention, and cost cap.

Any future change to the agreed feature scope should be an **explicit product decision**, tracked in the backlog/changelog, not an accidental deletion from a summary.

---

## 19. IMMEDIATE NEXT STEPS — SHORT, SEQUENTIAL

1. **Confirm this master plan as the baseline product scope.** We have now completed product idea consolidation; do not re-brainstorm already agreed features needlessly.
2. **Timebox platform choice** (responsive Web vs Flutter) using real reuse, dashboard UX, APK/demo needs and test/deploy constraints.
3. **Create the new shared GitHub repo** using the required structure; add collaborators, instructor/TA, README and initial project documents.
4. **Create the one Jira Scrum project** with roles, basic board and 4–5 prioritized backbone epics; create >=15 INVEST Stories (at least 12 visible for Week 4), and establish genuine Planning Poker estimates.
5. **Complete the urgent `docs/week4/` assignment**: photographed story map + MVP line, Jira screenshot, top 6 AC, INVEST/Planning Poker and forecast. Ensure every student submits through the instructor-required process.
6. **Execute Sprint 0 / Sprint 1 honestly as a catch-up effort** with short working increment(s), real individual PRs/tests and CI.
7. Follow Sprint 2–4 commitments; keep documenting code, feedback, testing and retrospectives at the time they occur; target polished Week 12 demo.
8. Start an **early OCR feasibility spike** with synthetic/redacted card images, since OCR is an especially important differentiator and potential technical risk.

---

## 20. AI HANDOFF INSTRUCTIONS

When this file is supplied in a new conversation:

1. Treat it as the **approved product-scope baseline**; don't erase previously agreed features or restart from a generic "four-feature school project" description.
2. Always distinguish **required course MVP**, **Priority 1/2/3 agreed enhancements**, and **open implementation decisions**.
3. Focus on a **student-first** productivity experience (team tasks, collaboration, evidence and timelines), while maintaining supervisor/coordinator functions.
4. University-ID OCR is high importance: preserve extraction of **name + university ID**, confirmation and manual fallback; honor test-only data rules. Never assert OCR alone validates identity or level.
5. Produce concise, sequential next steps in conversations; if writing Arabic to the user, avoid chaotic mid-sentence English and right-to-left text mixing. Put English terms/code in standalone lines or blocks.
6. For implementation, maintain required repository paths, GitHub/Jira traceability, real PR reviews, unit tests, Gherkin and CI; document every Sprint.
7. Never fabricate real user feedback, Jira activity, Planning Poker votes, member contributions, commits, approvals or test results.
8. If a course PDF/lab contradicts this plan, explicitly flag the discrepancy and defer to the source's mandatory academic constraint rather than quietly changing it.
9. The user wants to move **step by step**; do not dump huge unrelated instructions into ordinary chat responses.

---

*End of master plan — v1.0. Amend by explicit agreement, maintaining scope history.*
