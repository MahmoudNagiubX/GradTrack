# Week 4 - Selected User Stories

**Project:** GradTrack - Graduation Project Tracker  
**Jira project:** GT  
**Scope:** Six selected high-priority MVP stories from the GradTrack Jira backlog

GradTrack helps student teams manage graduation milestones and lets their assigned supervisor review the work. We selected these six stories because together they cover the main journey: create a team, assign a supervisor, view deadlines, submit work, and get approval. The full MVP has more stories than these six.

## GT-15 - Create a Student Team
**Agreed Story Points:** 3 points

**User story:** As a student, I want to create a graduation project team so that I can organize the project with my teammates.

**Acceptance criteria**
- A signed-in student can create a team with a name.
- The student who creates the team becomes its first member.
- The new team appears in that student's team list.

**Scenario 1 - Team created successfully**
```gherkin
Given I am signed in as a student
When I enter a valid team name and select Create Team
Then the team is created
And I appear as a member of that team
```

**Scenario 2 - Empty team name**
```gherkin
Given I am signed in as a student
When I try to create a team without entering a name
Then the system does not create the team
And it asks me to enter a team name
```

## GT-17 - Assign a Supervisor to a Team
**Agreed Story Points:** 2 points

**User story:** As a programme coordinator, I want to assign a supervisor to a team so that the team has someone responsible for reviewing its submissions.

**Acceptance criteria**
- An authorized coordinator can assign a supervisor to a team.
- The team page shows its currently assigned supervisor.
- Students cannot change their own supervisor assignment.

**Scenario 1 - Supervisor assigned**
```gherkin
Given I am signed in as a programme coordinator
And a team and a supervisor exist
When I assign that supervisor to the team
Then the team shows the selected supervisor
```

**Scenario 2 - Student tries to change supervisor**
```gherkin
Given I am signed in as a student
When I try to change my team's assigned supervisor
Then the system rejects the change
And the original supervisor stays assigned
```

## GT-18 - View Project Milestones and Deadlines
**Agreed Story Points:** 3 points

**User story:** As a student, I want to see my team's milestones and deadlines so that I know what needs to be finished next.

**Acceptance criteria**
- The page shows the milestone name, due date, and status.
- Milestones are listed in deadline order.
- An empty project shows a clear message instead of a broken or blank page.

**Scenario 1 - View upcoming milestones**
```gherkin
Given my team has Proposal, SRS, and Design milestones
When I open the Milestones page
Then I see their names, deadlines, and statuses
And they are ordered by deadline
```

**Scenario 2 - No milestones yet**
```gherkin
Given my team has no milestones
When I open the Milestones page
Then I see a message saying there are no milestones yet
```

## GT-20 - Submit a File or Link for a Milestone
**Agreed Story Points:** 5 points

**User story:** As a student, I want to submit a file or link for a milestone so that my supervisor can review our team's work.

**Acceptance criteria**
- Students can submit a supported file or a valid link.
- The system records the student, milestone, and submission time.
- An empty or invalid submission is rejected with a clear message.

**Scenario 1 - Submit the SRS**
```gherkin
Given I am a member of a team with an SRS milestone
When I submit a supported SRS file
Then the submission is saved under the SRS milestone
And the system records who submitted it and when
```

**Scenario 2 - Missing file or link**
```gherkin
Given I am submitting work for the SRS milestone
When I submit without a file or a valid link
Then the system does not save the submission
And it asks me to provide a file or link
```

## GT-21 - Mark Late Submissions
**Agreed Story Points:** 3 points

**User story:** As a supervisor, I want submissions made after the deadline to be marked late so that I can easily see when work arrived.

**Acceptance criteria**
- A submission after the saved deadline is automatically marked Late.
- A submission on or before the deadline is not marked Late.
- The submission timestamp and late status are saved.

**Scenario 1 - Submission is late**
```gherkin
Given the SRS deadline is 5:00 PM
When a student submits the SRS at 5:01 PM
Then the submission is saved
And it is marked Late
```

**Scenario 2 - Submission exactly on time**
```gherkin
Given the SRS deadline is 5:00 PM
When a student submits the SRS at exactly 5:00 PM
Then the submission is saved
And it is not marked Late
```

## GT-24 - Approve a Submission
**Agreed Story Points:** 5 points

**User story:** As the assigned supervisor, I want to approve a team's submission so that the team knows its milestone has been accepted.

**Acceptance criteria**
- Only the supervisor assigned to the team can approve its submission.
- Approval saves the supervisor's identity and the approval time.
- The team can see the Approved status.

**Scenario 1 - Assigned supervisor approves**
```gherkin
Given I am the supervisor assigned to Team A
And Team A has a submission waiting for review
When I approve that submission
Then the submission status becomes Approved
And my identity and the approval time are recorded
```

**Scenario 2 - Wrong supervisor tries to approve**
```gherkin
Given I am a supervisor who is not assigned to Team A
And Team A has a submission waiting for review
When I try to approve that submission
Then the system rejects my action
And the submission keeps its previous status
```

---

**Estimation note:** The team reported the agreed points for these six stories after Planning Poker. The scenarios describe the expected behavior and are not yet automated test results.