"""Team-authorized submission creation, history, and private downloads."""

from __future__ import annotations

import logging
import re
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, BinaryIO
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask
from starlette.datastructures import FormData, UploadFile
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.formparsers import MultiPartException, MultiPartParser

from app.auth import CurrentUser
from app.config import Settings
from app.database import get_db_session
from app.models import (
    Milestone,
    MilestoneSubmission,
    SubmissionVersion,
    TeamMembership,
    User,
)
from app.schemas import LinkSubmissionRequest, SubmissionVersionResponse
from app.submission_storage import (
    MAX_FILE_SIZE_BYTES,
    MAX_MULTIPART_OVERHEAD_BYTES,
    FileValidationError,
    PrivateStorageUnavailable,
    StagedUpload,
    open_stored_file,
    stage_upload,
)
from app.teams import get_visible_team

logger = logging.getLogger("gradtrack.submissions")
router = APIRouter(
    prefix="/teams/{team_id}/milestones/{milestone_id}/submissions",
    tags=["submissions"],
)

DbSession = Annotated[Session, Depends(get_db_session)]


@dataclass(frozen=True, slots=True)
class SubmissionAccess:
    """Authenticated caller and the team-owned milestone in the request path."""

    current_user: User
    milestone: Milestone
    session: Session


def _submission_access(
    team_id: UUID,
    milestone_id: UUID,
    current_user: User,
    session: Session,
) -> SubmissionAccess:
    get_visible_team(team_id, current_user, session)
    milestone = session.scalar(
        select(Milestone).where(
            Milestone.id == milestone_id,
            Milestone.team_id == team_id,
        )
    )
    if milestone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Milestone not found",
        )
    return SubmissionAccess(current_user, milestone, session)


def get_submission_reader_access(
    team_id: UUID,
    milestone_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> SubmissionAccess:
    """Require current team visibility before reading submissions."""
    return _submission_access(team_id, milestone_id, current_user, session)


def get_submission_writer_access(
    team_id: UUID,
    milestone_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> SubmissionAccess:
    """Require an active student who currently belongs to the owning team."""
    access = _submission_access(team_id, milestone_id, current_user, session)
    if current_user.system_role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a team student can submit this milestone",
        )
    membership_id = session.scalar(
        select(TeamMembership.id).where(
            TeamMembership.team_id == team_id,
            TeamMembership.user_id == current_user.id,
        )
    )
    if membership_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Milestone not found",
        )
    return access


SubmissionReader = Annotated[SubmissionAccess, Depends(get_submission_reader_access)]
SubmissionWriter = Annotated[SubmissionAccess, Depends(get_submission_writer_access)]


def _create_initial_submission(
    access: SubmissionAccess,
    *,
    source_type: str,
    url: str | None = None,
    staged_upload: StagedUpload | None = None,
) -> SubmissionVersionResponse:
    """Persist version one while holding the milestone deadline row lock."""
    session = access.session
    milestone = session.scalar(
        select(Milestone)
        .where(
            Milestone.id == access.milestone.id,
            Milestone.team_id == access.milestone.team_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if milestone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Milestone not found",
        )

    user = session.scalar(
        select(User)
        .where(User.id == access.current_user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    membership_id = session.scalar(
        select(TeamMembership.id).where(
            TeamMembership.team_id == milestone.team_id,
            TeamMembership.user_id == user.id,
        )
    )
    if user.system_role != "student" or membership_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Milestone not found",
        )

    exists = session.scalar(
        select(MilestoneSubmission.id).where(
            MilestoneSubmission.milestone_id == milestone.id
        )
    )
    if exists is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A submission already exists for this milestone",
        )

    submitted_at = _now_utc()
    deadline = _as_utc(milestone.due_at)
    submission = MilestoneSubmission(
        milestone_id=milestone.id,
        review_status="pending_review",
    )
    session.add(submission)

    try:
        session.flush()
        version = SubmissionVersion(
            submission_id=submission.id,
            version_number=1,
            submitted_by=user.id,
            submitted_at=submitted_at,
            deadline_at_submission=deadline,
            is_late=submitted_at > deadline,
            source_type=source_type,
            storage_key=staged_upload.storage_key if staged_upload else None,
            original_filename=(
                staged_upload.original_filename if staged_upload else None
            ),
            file_size_bytes=(staged_upload.file_size_bytes if staged_upload else None),
            media_type=staged_upload.media_type if staged_upload else None,
            url=url,
        )
        session.add(version)
        session.flush()
        if staged_upload is not None:
            staged_upload.promote()
        session.commit()
        if staged_upload is not None:
            staged_upload.committed = True
        return _serialize_version(version, submission.review_status, milestone)
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A submission already exists for this milestone",
        ) from None
    except SQLAlchemyError as error:
        session.rollback()
        logger.error(
            "Submission persistence failed: exception=%s", type(error).__name__
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Submission could not be saved",
        ) from None
    except PrivateStorageUnavailable:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Private file storage is unavailable",
        ) from None
    except HTTPException:
        session.rollback()
        raise
    except Exception as error:
        session.rollback()
        logger.error("Submission processing failed: exception=%s", type(error).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Submission could not be saved",
        ) from None


def _serialize_version(
    version: SubmissionVersion,
    review_status: str,
    milestone: Milestone,
) -> SubmissionVersionResponse:
    return SubmissionVersionResponse(
        id=version.id,
        submission_id=version.submission_id,
        milestone_id=milestone.id,
        team_id=milestone.team_id,
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
        review_status=review_status,
    )


def _get_version(
    access: SubmissionAccess, version_id: UUID
) -> tuple[SubmissionVersion, str] | None:
    result = access.session.execute(
        select(SubmissionVersion, MilestoneSubmission.review_status)
        .join(
            MilestoneSubmission,
            MilestoneSubmission.id == SubmissionVersion.submission_id,
        )
        .where(
            MilestoneSubmission.milestone_id == access.milestone.id,
            SubmissionVersion.id == version_id,
        )
    ).first()
    return (result[0], result[1]) if result is not None else None


@router.post(
    "/link",
    response_model=SubmissionVersionResponse,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"description": "A first submission already exists"}},
)
def submit_link(
    payload: LinkSubmissionRequest,
    access: SubmissionWriter,
) -> SubmissionVersionResponse:
    """Accept the first version of a milestone submission as an HTTPS link."""
    return _create_initial_submission(
        access,
        source_type="link",
        url=payload.url,
    )


class UploadRequestTooLarge(Exception):
    """The complete multipart body exceeded the bounded parser allowance."""


async def _single_file_upload(request: Request) -> AsyncIterator[UploadFile]:
    """Parse only one `file` part and close its temporary upload after the route."""
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            declared_length = int(content_length)
        except ValueError:
            declared_length = 0
        if declared_length > MAX_FILE_SIZE_BYTES + MAX_MULTIPART_OVERHEAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="The uploaded file exceeds the 20 MiB limit",
            )

    async def bounded_stream() -> AsyncIterator[bytes]:
        received_bytes = 0
        async for chunk in request.stream():
            received_bytes += len(chunk)
            if received_bytes > MAX_FILE_SIZE_BYTES + MAX_MULTIPART_OVERHEAD_BYTES:
                raise UploadRequestTooLarge
            yield chunk

    try:
        parser = MultiPartParser(
            headers=request.headers,
            stream=bounded_stream(),
            max_files=1,
            max_fields=0,
        )
        form: FormData = await parser.parse()
    except UploadRequestTooLarge:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="The uploaded request exceeds the 20 MiB limit",
        ) from None
    except (
        StarletteHTTPException,
        MultiPartException,
        UnicodeDecodeError,
        ValueError,
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A single multipart file named 'file' is required",
        ) from None

    items = list(form.multi_items())
    if (
        len(items) != 1
        or items[0][0] != "file"
        or not isinstance(items[0][1], UploadFile)
    ):
        await form.close()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A single multipart file named 'file' is required",
        )

    try:
        yield items[0][1]
    finally:
        await form.close()


FileUpload = Annotated[UploadFile, Depends(_single_file_upload)]


@router.post(
    "/file",
    response_model=SubmissionVersionResponse,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["file"],
                        "properties": {"file": {"type": "string", "format": "binary"}},
                    }
                }
            },
        }
    },
    responses={
        409: {"description": "A first submission already exists"},
        413: {"description": "The upload exceeds the 20 MiB limit"},
        422: {"description": "The file is invalid or unsupported"},
        503: {"description": "Private storage is unavailable"},
    },
)
def submit_file(
    access: SubmissionWriter,
    upload: FileUpload,
) -> SubmissionVersionResponse:
    """Stream, validate, and privately store the first file submission."""
    staged: StagedUpload | None = None
    try:
        staged = stage_upload(
            upload.file,
            filename=upload.filename,
            content_type=upload.content_type,
            configured_dir=Settings.from_environment().private_upload_dir,
        )
        return _create_initial_submission(
            access,
            source_type="file",
            staged_upload=staged,
        )
    except FileValidationError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=str(error),
        ) from None
    except PrivateStorageUnavailable:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Private file storage is unavailable",
        ) from None
    finally:
        if staged is not None:
            staged.cleanup()


@router.get("", response_model=list[SubmissionVersionResponse])
def list_submissions(access: SubmissionReader) -> list[SubmissionVersionResponse]:
    """List the team's immutable submission versions oldest to newest."""
    rows = access.session.execute(
        select(SubmissionVersion, MilestoneSubmission.review_status)
        .join(
            MilestoneSubmission,
            MilestoneSubmission.id == SubmissionVersion.submission_id,
        )
        .where(MilestoneSubmission.milestone_id == access.milestone.id)
        .order_by(SubmissionVersion.submitted_at, SubmissionVersion.id)
    ).all()
    return [
        _serialize_version(version, review_status, access.milestone)
        for version, review_status in rows
    ]


@router.get("/{version_id}", response_model=SubmissionVersionResponse)
def read_submission(
    version_id: UUID,
    access: SubmissionReader,
) -> SubmissionVersionResponse:
    """Return metadata only for a version owned by this milestone."""
    result = _get_version(access, version_id)
    if result is None:
        raise _version_not_found()
    version, review_status = result
    return _serialize_version(version, review_status, access.milestone)


@router.get(
    "/{version_id}/download",
    response_class=StreamingResponse,
    responses={
        404: {"description": "File submission not found"},
        503: {"description": "Private storage is unavailable"},
    },
)
def download_submission(
    version_id: UUID,
    access: SubmissionReader,
) -> StreamingResponse:
    """Stream an authorized private file version as a safe attachment."""
    result = _get_version(access, version_id)
    if result is None:
        raise _version_not_found()
    version, _ = result
    if version.source_type != "file" or version.storage_key is None:
        raise _version_not_found()

    try:
        source = open_stored_file(
            Settings.from_environment().private_upload_dir,
            version.storage_key,
        )
    except PrivateStorageUnavailable:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Submission file is unavailable",
        ) from None

    try:
        file_size = source.seek(0, 2)
        source.seek(0)
    except OSError:
        source.close()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Submission file is unavailable",
        ) from None
    if file_size != version.file_size_bytes:
        source.close()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Submission file is unavailable",
        )
    filename = version.original_filename or "submission"
    disposition = _content_disposition(filename)
    headers = {
        "Content-Disposition": disposition,
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "no-store",
        "Content-Length": str(version.file_size_bytes),
    }
    return StreamingResponse(
        _file_chunks(source),
        media_type="application/octet-stream",
        headers=headers,
        background=BackgroundTask(source.close),
    )


def _file_chunks(source: BinaryIO) -> Iterator[bytes]:
    try:
        while chunk := source.read(1024 * 1024):
            yield chunk
    finally:
        source.close()


def _content_disposition(filename: str) -> str:
    ascii_fallback = re.sub(r"[^A-Za-z0-9._-]", "_", filename).strip("._")
    if not ascii_fallback:
        ascii_fallback = "submission"
    return (
        f'attachment; filename="{ascii_fallback}"; '
        f"filename*=UTF-8''{quote(filename, safe='')}"
    )


def _version_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Submission version not found",
    )


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC)
