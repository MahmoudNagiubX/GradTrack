"""Domain checks for supervisor assignment persistence."""

from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import SupervisorAssignment, User


def assign_supervisor(
    session: Session,
    team_id: UUID,
    supervisor_id: UUID,
) -> SupervisorAssignment:
    """Create or replace the current assignment for a supervisor-role user."""
    supervisor = session.get(User, supervisor_id)
    if supervisor is None or supervisor.system_role != "supervisor":
        raise ValueError("assigned user must have the supervisor system role")

    assignment = session.get(SupervisorAssignment, team_id)
    if assignment is None:
        assignment = SupervisorAssignment(
            team_id=team_id,
            supervisor_id=supervisor_id,
        )
    else:
        assignment.supervisor_id = supervisor_id
        assignment.assigned_at = func.now()

    session.add(assignment)
    return assignment
