"""Database-independent review request and response contracts."""

import pytest
from app.main import app
from app.schemas import ReviewDecisionRequest, SubmissionVersionResponse
from pydantic import ValidationError


def test_return_review_requires_trimmed_feedback() -> None:
    request = ReviewDecisionRequest(
        decision="returned", feedback="  Revise section 2.  "
    )

    assert request.feedback == "Revise section 2."

    for feedback in (None, "", "   "):
        with pytest.raises(ValidationError):
            ReviewDecisionRequest(decision="returned", feedback=feedback)


def test_review_feedback_limits_and_approval_blank_normalization() -> None:
    assert ReviewDecisionRequest(decision="returned", feedback="x").feedback == "x"
    assert (
        ReviewDecisionRequest(decision="returned", feedback="x" * 2000).feedback
        == "x" * 2000
    )
    with pytest.raises(ValidationError):
        ReviewDecisionRequest(decision="returned", feedback="x" * 2001)

    assert ReviewDecisionRequest(decision="approved").feedback is None
    assert ReviewDecisionRequest(decision="approved", feedback="  ").feedback is None
    with pytest.raises(ValidationError):
        ReviewDecisionRequest(decision="approved", feedback="x" * 2001)


def test_review_request_rejects_other_decisions_and_forged_audit_fields() -> None:
    with pytest.raises(ValidationError):
        ReviewDecisionRequest(decision="pending_review")

    with pytest.raises(ValidationError):
        ReviewDecisionRequest(
            decision="approved",
            feedback="Accepted",
            reviewer_id="00000000-0000-0000-0000-000000000001",
        )


@pytest.mark.parametrize("review_status", ["pending_review", "returned", "approved"])
def test_submission_version_response_supports_version_specific_statuses(
    review_status: str,
) -> None:
    response = SubmissionVersionResponse(
        id="00000000-0000-0000-0000-000000000001",
        submission_id="00000000-0000-0000-0000-000000000002",
        milestone_id="00000000-0000-0000-0000-000000000003",
        team_id="00000000-0000-0000-0000-000000000004",
        version_number=1,
        submitted_by="00000000-0000-0000-0000-000000000005",
        submitted_at="2026-12-01T15:00:00Z",
        deadline_at_submission="2026-12-01T15:00:00Z",
        is_late=False,
        source_type="link",
        original_filename=None,
        file_size_bytes=None,
        media_type=None,
        url="https://example.org/submission",
        review_status=review_status,
    )

    assert response.review_status == review_status


def test_review_routes_are_described_in_openapi() -> None:
    paths = app.openapi()["paths"]

    assert "/supervisor/submissions/pending" in paths
    assert (
        "/teams/{team_id}/milestones/{milestone_id}/submissions/{version_id}/review"
    ) in paths
    assert (
        "/teams/{team_id}/milestones/{milestone_id}/submissions/revisions/link"
    ) in paths
    assert (
        "/teams/{team_id}/milestones/{milestone_id}/submissions/revisions/file"
    ) in paths
