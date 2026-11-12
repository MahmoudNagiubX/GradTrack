# Week 4 - Story Estimation and INVEST Review

**Project:** GradTrack - Graduation Project Tracker  
**Jira:** GT  
**Team:** Mahmoud (Product Owner), Mirette Magdy (Scrum Master), Kareem Waleed and Seif Salah (Developers)

## 1. How we estimated

We used Planning Poker with Fibonacci story points (1, 2, 3, 5, 8, 13). A point describes the relative size of a story, including work, complexity and uncertainty. It does not mean a fixed number of hours.

Mahmoud owns the story priorities and explains what the user needs. Kareem and Seif provide the Developer estimates; Mirette coordinates the estimation activity. The team reported that its **final agreed points matched the estimates already proposed in Jira**.

## 2. Agreed results for the six selected stories

| Jira ID | Story | Earlier Jira estimate | Final agreed points | Why this size makes sense |
|---|---|---:|---:|---|
| GT-15 | Create a Student Team | 3 | **3** | Team creation, basic validation and saving membership. |
| GT-17 | Assign a Supervisor to a Team | 2 | **2** | Small user flow, but permissions still need checking. |
| GT-18 | View Project Milestones and Deadlines | 3 | **3** | Display, sort and handle an empty list. |
| GT-20 | Submit a File or Link for a Milestone | 5 | **5** | Two input paths, file handling and submission history. |
| GT-21 | Mark Late Submissions | 3 | **3** | Date comparison and deadline boundary tests. |
| GT-24 | Approve a Submission | 5 | **5** | Approval status, audit details and the assigned-supervisor rule. |
| **Total** | **6 stories** | **21** | **21** | |

**Planning Poker record:** We have the six agreed consensus values. The individual first-round cards, any re-votes and the session date were not provided for this document, so they are not reconstructed here. No estimate changed from the initial proposal. These values are final for the six selected stories; the rest of the Jira backlog still uses planning estimates unless separately confirmed.

## 3. INVEST check

We checked whether the selected stories are Independent, Negotiable, Valuable, Estimable, Small and Testable. The notes focus on possible issues, rather than treating every story as perfect.

| Story | I | N | V | E | S | T | Our note |
|---|---|---|---|---|---|---|---|
| GT-15 | Yes | Yes | Yes | Yes | Yes | Yes | Use a signed-in student in the test. |
| GT-17 | Mostly | Yes | Yes | Yes | Yes | Yes | Needs an existing team and a coordinator account. |
| GT-18 | Yes | Yes | Yes | Yes | Yes | Yes | Test with several milestones and no milestones. |
| GT-20 | Mostly | Yes | Yes | Yes | Check | Yes | File upload and URL submission may need splitting. |
| GT-21 | Mostly | Yes | Yes | Yes | Yes | Yes | Test just before, exactly at and after the deadline. |
| GT-24 | Mostly | Yes | Yes | Yes | Check | Yes | The server must reject approval by the wrong supervisor. |

**I / Independent:** Stories can be tested with prepared sample data, even when one flow naturally comes after another.  
**N / Negotiable:** The team can still discuss validation, UI details and implementation.  
**V / Valuable:** Each gives a useful action or clear information to students or supervisors.  
**E / Estimable:** We have enough information for an initial size.  
**S / Small:** Most should fit a Sprint; GT-20 and GT-24 need close attention.  
**T / Testable:** Each has acceptance criteria and Given-When-Then scenarios in `stories.md`.

## 4. Stories we might split

- **GT-20 (5 points):** If needed, split into *Submit a Link* and *Upload a File* using the SPIDR **Paths** idea. Each should remain a working end-to-end action.
- **GT-24 (5 points):** Keep the approval rule together with the approval action. If it becomes too large, split by a meaningful user path, not into separate frontend and backend stories.
- If a later story reaches **13 points or more**, we will refine or split it before committing it to a Sprint.

## 5. Backlog totals

| Scope | Stories | Current points | Estimate status |
|---|---:|---:|---|
| Six selected stories | 6 | 21 | Team-reported agreed values |
| Remaining required MVP stories | 5 | 14 | Current Jira planning values |
| Future-release stories | 13 | 44 | Current Jira planning values |
| **Whole backlog** | **24** | **79** | **Mixed agreed and provisional values** |

We will update the other estimates after further refinement and use completed work from the first Sprint to improve future forecasts.