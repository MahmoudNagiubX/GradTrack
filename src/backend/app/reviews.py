"""Version-scoped supervisor decisions for team submissions."""

import logging
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, aliased

from app.auth import CurrentUser
from app.database import get_db_session
from app.models import (
    Milestone,
    MilestoneSubmission,
    SubmissionVersion,
    SupervisorAssignment,
    SupervisorReview,
    Team,
    User,
)
from app.schemas import (
    PendingSubmissionResponse,
    ReviewDecisionRequest,
    SupervisorReviewResponse,
)
from app.teams import get_visible_team

DbSession = Annotated[Session, Depends(get_db_session)]
logger = logging.getLogger("gradtrack.reviews")

pending_router = APIRouter(prefix="/supervisor/submissions", tags=["reviews"])
review_router = APIRouter(
    prefix=(
        "/teams/{team_id}/milestones/{milestone_id}/submissions/{version_id}/review"
    ),
    tags=["reviews"],
)


@pending_router.get("/pending", response_model=list[PendingSubmissionResponse])
def list_pending_submissions(
    current_user: CurrentUser,
    session: DbSession,
) -> list[PendingSubmissionResponse]:
    """List each assigned supervisor's current, unreviewed version."""
    if current_user.system_role != "supervisor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized for this resource",
        )

    latest_submission_version = aliased(SubmissionVersion)
    latest_version_id = (
        select(latest_submission_version.id)
        .where(
            latest_submission_version.submission_id == MilestoneSubmission.id,
        )
        .order_by(latest_submission_version.version_number.desc())
        .limit(1)
        .correlate(MilestoneSubmission)
        .scalar_subquery()
    )
    reviewed_version = select(SupervisorReview.id).where(
        SupervisorReview.version_id == SubmissionVersion.id
    )
    rows = session.execute(
        select(SubmissionVersion, Team, Milestone, User.display_name)
        .join(
            MilestoneSubmission,
            MilestoneSubmission.id == SubmissionVersion.submission_id,
        )
        .join(Milestone, Milestone.id == MilestoneSubmission.milestone_id)
        .join(Team, Team.id == Milestone.team_id)
        .join(SupervisorAssignment, SupervisorAssignment.team_id == Team.id)
        .join(User, User.id == SubmissionVersion.submitted_by)
        .where(
            SupervisorAssignment.supervisor_id == current_user.id,
            MilestoneSubmission.review_status == "pending_review",
            SubmissionVersion.id == latest_version_id,
            ~reviewed_version.exists(),
        )
        .order_by(SubmissionVersion.submitted_at, SubmissionVersion.id)
    ).all()
    return [
        _serialize_pending(version, team, milestone, submitter_name)
        for version, team, milestone, submitter_name in rows
    ]


@review_router.post(
    "",
    response_model=SupervisorReviewResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"description": "Submission version not found"},
        409: {"description": "Submission is no longer awaiting this review"},
    },
)
def decide_submission(
    team_id: UUID,
    milestone_id: UUID,
    version_id: UUID,
    payload: ReviewDecisionRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> SupervisorReviewResponse:
    """Record one immutable decision from the team's currently assigned supervisor."""
    parent = _locked_submission_for_version(session, team_id, milestone_id, version_id)
    if parent is None:
        raise _version_not_found()

    reviewer = _refresh_user_after_lock(session, current_user.id)
    if reviewer is None or not reviewer.is_active:
        raise _credentials_error()
    if reviewer.system_role != "supervisor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized for this resource",
        )

    assignment = session.scalar(
        select(SupervisorAssignment)
        .where(SupervisorAssignment.team_id == team_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if assignment is None or assignment.supervisor_id != reviewer.id:
        raise _version_not_found()

    latest_version_id = session.scalar(
        select(SubmissionVersion.id)
        .where(SubmissionVersion.submission_id == parent.id)
        .order_by(SubmissionVersion.version_number.desc())
        .limit(1)
    )
    if parent.review_status != "pending_review" or latest_version_id != version_id:
        raise _review_conflict()

    review = SupervisorReview(
        version_id=version_id,
        reviewer_id=reviewer.id,
        decision=payload.decision,
        feedback=payload.feedback,
        reviewed_at=datetime.now(UTC),
    )
    parent.review_status = payload.decision
    session.add(review)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise _review_conflict() from None
    except SQLAlchemyError as error:
        session.rollback()
        logger.error("Review persistence failed: exception=%s", type(error).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Review could not be saved",
        ) from None

    return _serialize_review(review)


@review_router.get("", response_model=SupervisorReviewResponse)
def read_submission_review(
    team_id: UUID,
    milestone_id: UUID,
    version_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> SupervisorReviewResponse:
    """Read a decision only through a currently visible team and its version."""
    get_visible_team(team_id, current_user, session)
    review = session.scalar(
        select(SupervisorReview)
        .join(
            SubmissionVersion,
            SubmissionVersion.id == SupervisorReview.version_id,
        )
        .join(
            MilestoneSubmission,
            MilestoneSubmission.id == SubmissionVersion.submission_id,
        )
        .join(Milestone, Milestone.id == MilestoneSubmission.milestone_id)
        .where(
            Milestone.team_id == team_id,
            MilestoneSubmission.milestone_id == milestone_id,
            SubmissionVersion.id == version_id,
        )
    )
    if review is None:
        raise _version_not_found()
    return _serialize_review(review)


def _locked_submission_for_version(
    session: Session,
    team_id: UUID,
    milestone_id: UUID,
    version_id: UUID,
) -> MilestoneSubmission | None:
    return session.scalar(
        select(MilestoneSubmission)
        .join(Milestone, Milestone.id == MilestoneSubmission.milestone_id)
        .join(
            SubmissionVersion,
            SubmissionVersion.submission_id == MilestoneSubmission.id,
        )
        .where(
            Milestone.team_id == team_id,
            Milestone.id == milestone_id,
            SubmissionVersion.id == version_id,
        )
        .with_for_update(of=MilestoneSubmission)
        .execution_options(populate_existing=True)
    )


def _refresh_user_after_lock(session: Session, user_id: UUID) -> User | None:
    return session.scalar(
        select(User)
        .where(User.id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def _serialize_pending(
    version: SubmissionVersion,
    team: Team,
    milestone: Milestone,
    submitter_name: str,
) -> PendingSubmissionResponse:
    return PendingSubmissionResponse(
        id=version.id,
        submission_id=version.submission_id,
        milestone_id=milestone.id,
        team_id=team.id,
        version_number=version.version_number,
        submitted_by=version.submitted_by,
        submitted_at=_as_utc(version.submitted_at),
        deadline_at_submission=_as_utc(version.deadline_at_submission),
        is_late=version.is_late,
        source_type=version.source_type,
        original_filename=version.original_filename,
        file_size_bytes=version.file_size_bytes,
        media_type=version.media_type,
        url=version.url,
        review_status="pending_review",
        team_name=team.name,
        milestone_name=milestone.name,
        submitter_name=submitter_name,
    )


def _serialize_review(review: SupervisorReview) -> SupervisorReviewResponse:
    return SupervisorReviewResponse(
        id=review.id,
        version_id=review.version_id,
        reviewer_id=review.reviewer_id,
        decision=review.decision,
        feedback=review.feedback,
        reviewed_at=_as_utc(review.reviewed_at),
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC)


def _version_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Submission version not found",
    )


def _review_conflict() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Submission is no longer awaiting this review",
    )


def _credentials_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
