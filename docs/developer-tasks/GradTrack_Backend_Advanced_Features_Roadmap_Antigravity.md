# GradTrack — Advanced Backend Feature Roadmap (before React / Flutter)

**Prepared:** 2026-11-21  
**Product direction:** Fully functional local university course demo; Python FastAPI + PostgreSQL 16 + private local file storage, no cloud deployment required.  
**Authority:** Master Plan §§5.1–5.11, Priority 1–3, live Jira stories and newer PO direction: **finish desired backend enhancements before React/Flutter**. This roadmap does **not** authorize implementing all features at once. Give Antigravity a separate reviewed task specification per step.

## Current verified core (not an instruction to reimplement)

Core backend Phases 0–7B: manual auth, teams/members/leader and supervisor assignment, milestones/deadlines, secure milestone file/link submissions, late flags/snapshots, supervisor return/approval/versioned revisions, tasks/status/assignment/checklists/subtasks/comments/attachments, team calendar/progress, supervisor portfolio, 7-day student deadline reminders/read receipts. Local PostgreSQL 16.11 demo report states 289 passing tests + 1 symlink skip and successful full HTTP journey/restart persistence; latest PR #12 CI passed with 290 tests. All PRs #2–#12 remain stacked and unmerged at last inspection.

## Sequence and clearly bounded phase gates

| Order | Source | Subphase | Minimum backend result | Complexity / dependency |
|---|---|---|---|---|
| **1** | GT-32 / Master §5.1 | User profile & avatar | Edit allowed profile fields; authenticated/local PNG/JPEG avatar, team-scoped reads; no role escalation | Start now. Complete separate GT-32 spec |
| **2** | GT-33 / Master §5.1 | OCR feasibility **spike** | Evaluate candidate offline Arabic/English OCR on synthetic university-ID-like images, report name/number accuracy, latency, memory; compare fallback without claims of verification | Experiment only; do not rush a large OCR dependency into main backend |
| **3** | GT-34 / Master §5.8 | Task focus sessions | Start/pause/resume/finish sessions, server timestamps and genuine elapsed duration, own history, optional task link; no daemon | Small additive PostgreSQL table/API |
| **4** | GT-35 / Master §5.9 | Hardware inventory & purchases | Team-scoped component/purchase items, quantity/status/expected vs actual cost, ordered/received, local demo budget summary | Optional per team; no real payments |
| **5** | GT-38 / Master §5.5 | Meeting notes, decisions and action items | Team meeting record/note and a due-dated action item with owner, optional link to existing task; simple read/write permissions | Prepare source notes for GT-36 |
| **6** | GT-33 / Master §5.1 | University ID OCR integration | Review/correct OCR-suggested name/student number; manual fallback; synthetic test cards; transient images by default | Only after spike demonstrates an acceptable local approach |
| **7** | GT-36 / Master §5.10 | Meeting summary assistant | Suggested summary of provided notes, editable/rejectable, no auto-save decisions/assignments | Need approved local model/provider vs transparent deterministic non-AI fallback; don't fake 'AI' |
| **8** | Master §§5.5, 5.6, 5.7 | Collaboration/analytics enhancements | Shared project documents, meeting decision log, coordinator dashboard, non-deadline in-app assignment/comment/review alerts; reuse existing auth/storage/activity | Split into small Jira-scoped task files before coding |
| **9** | Master §5.3 | Richer dependencies / timeline backend | Optional one-level task dependencies and timeline conflict data if frontend plan requires it; don't create duplicate Gantt database | Design with front-end expectations when known |
| **10** | Master §5.11 | Coordinator grading/reporting | Access-controlled rubric/evaluation and basic reports, never visible to unrelated teams | Explicit rules and actor approval before implementation |
| **11** | Master §5.1 | Google OpenID Connect + email OTP/recovery | True Google identity validation and real email verification/recovery only with properly configured credentials/provider or explicit local demo policy | External accounts/SMTP may be required; **do not invent credentials or pretend a mocked provider is real** |

This order is a sensible default, not a statement that all optional enhancements are required by the faculty. GT-33 feasibility runs early; its full implementation waits until the approach is proven. GT-36 depends on GT-38 notes. The optional Grading and OAuth/OTP features need separate product/technical decisions and should be explicitly authorized.

## Engineering rules to protect the project

1. **One Jira story or tightly related task per PR.** No giant prompt for all advanced features. Verify existing code, Master Plan, Jira acceptance criteria and reference project before every phase.
2. **Only real functionality.** A GT-36 fake hardcoded string is not an AI summarizer. A mocked Google account is not Google Sign-In. Label demos and fallbacks honestly.
3. **No production infrastructure creep.** Local PostgreSQL and private files suffice; no microservices, Kubernetes, Redis, queues, cloud deployment, subscriptions or vendor credentials without demonstrated benefit and explicit PO approval.
4. **Minimal schemas and APIs.** Reuse `User`, `Task`, `Team`, `Milestone`, existing role checking and local attachment storage; add focused Alembic migrations and real authorization tests. No unnecessary repository layers or database copies.
5. **Keep test evidence truthful.** Run local PostgreSQL integration plus exact-head GitHub Actions CI; supplement with real HTTP demo paths for each user-facing feature. If human/manual verification remains, say so.
6. **Never merge automatically.** PRs #2–#12 are unmerged as last checked. Branch from newest verified head for staged dependency development if explicitly authorized, or from integrated `develop` if already approved/merged. Human peer review and sequential integration remain essential. The larger the stack gets, the greater the chance of conflicts.
7. **Protect synthetic student data.** University-ID OCR tests use fictional/redacted cards only. OCR text is an editable suggestion, not official proof. Don't commit credentials, ID images or user-uploaded files.
8. **Frontend remains required.** Backend-first is the approved immediate sequence but should not erase the React main web dashboard, Flutter mobile companion or final Agile demo obligations. Do not claim a backend-only repo satisfies full project completion.
9. **Jira correctness.** Existing story point estimates are draft, not developer-agreed; don't fabricate votes, sprint outcomes, reviews or contributors. Mark In Review only when submitted; Done only after team Definition of Done.
10. **Before major optional providers/dependencies**, report concrete local setup burden, actual security/privacy implications and demo suitability; propose the minimum viable feature and request the PO's approval.

## What happens next

**Start with:** `GradTrack_GT32_Profile_Backend_Antigravity.md`. After receiving GT-32 execution report, verify actual PR/CI and implementation; then prepare a separate short **GT-33 OCR feasibility spike specification**, followed by the next prioritized backend story. No frontend development in the current task.
