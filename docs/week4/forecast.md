# Week 4 - Sprint Forecast

**Project:** GradTrack - Graduation Project Tracker  
**Jira:** GT  
**Forecast status:** Proposed plan, to be checked against the team's actual capacity

## 1. Backlog we are planning from

| Scope | User stories | Story points |
|---|---:|---:|
| Required MVP | 11 | 35 |
| Future releases | 13 | 44 |
| **Total** | **24** | **79** |

The **six selected MVP stories (21 points)** were confirmed by the team after Planning Poker. The **remaining 18 stories (58 points)** still use the current Jira planning estimates. These figures match the current backlog screenshots; estimates can change during refinement.

The MVP is the complete path from team setup and supervisor assignment to milestones, file/link submission, late detection, supervisor feedback and approval or return. The key rules are: a late submission must be flagged, and only the team's assigned supervisor can approve it.

## 2. Time and velocity assumption

Sprint 0 is for setup and planning. The course then has **four one-week development Sprints (Sprint 1 to Sprint 4)**. We want to complete the required MVP by the end of Sprint 3 and leave Sprint 4 for improvements and fixes.

Because the team does not have a completed development Sprint yet, we are using **12 points per Sprint as an initial baseline assumption**, **not a measured velocity**. We will revise this number after Sprint 1. We must also check how much time each member actually has before committing Sprint scope.

## 3. Suggested Sprint breakdown

This is a planning proposal; story assignments are not a claim that these items are already committed in Jira.

| Sprint | Proposed stories | Points | Main goal |
|---|---|---:|---|
| Sprint 1 | GT-15, GT-16, GT-17, GT-18 | 11 | Create a team, connect a supervisor and view milestones. |
| Sprint 2 | GT-19, GT-20, GT-21, GT-22 | 13 | Set deadlines, submit work, flag late submissions and show pending reviews. |
| Sprint 3 | GT-23, GT-24, GT-25 | 11 | Return work with feedback, approve work and submit a corrected version. |
| Sprint 4 | Selected fixes and future-release stories | To decide | Improve the product using actual feedback and remaining capacity. |
| **Required MVP** | **11 stories** | **35** | |

Sprint 2 is **one point above** the assumed 12-point baseline. If Sprint 1 shows slower progress, we should reduce or rearrange work rather than pretending the original forecast was accurate.

## 4. Capacity and remaining work

At an assumed 12 points per Sprint:

- MVP workload: `35 / 12 = 2.92` Sprints, roughly **3 development Sprints**.
- Whole backlog: `79 / 12 = 6.58` Sprints, roughly **7 development Sprints**.
- Available development Sprints: **4** (Sprint 1-4).
- Illustrative four-Sprint capacity: `4 x 12 = 48` points.
- Gap to the whole current backlog: `79 - 48 = 31` points.

The course timeline therefore does not support promising every planned feature. Delivering the required MVP is the priority; extra features can follow if time and testing allow.

**Actual capacity check before Sprint Planning:** The team still needs to agree on availability around lectures, exams and other commitments. No individual hours or measured velocity are assumed in this report.

## 5. Risks and decisions for the next planning meeting

- **Basic login:** The current GT-32 account/profile story is below the MVP line, but the MVP needs a minimal way for students and supervisors to sign in. We should split a small *Basic Sign-In* story and move it above the MVP line. Its points are **not included** in the current 35-point MVP total.
- **Upload and approval:** File handling, secure permissions and approval audit records may be harder than the draft points suggest.
- **Team experience:** Kareem and Seif are beginners. We should give them small real development and testing contributions while Mahmoud supports integration and complex tasks.
- **Product focus:** The React web app is the main experience. The smaller Flutter companion app, OCR and AI features should not delay the MVP.

## 6. Reflection

Our 79-point backlog is larger than the work we can reasonably plan across four development Sprints. We chose the milestone and supervisor workflow first because those features solve the main problem and are required for the course. The 12-point figure is a starting assumption, not a record of previous performance. After Sprint 1 we will compare this forecast with actual completed points and update our priorities.