"""Manual student authentication and reusable authorization dependencies."""

import logging
from collections.abc import AsyncIterator, Callable, Iterator
from typing import Annotated, BinaryIO
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask
from starlette.datastructures import FormData, UploadFile
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.formparsers import MultiPartException, MultiPartParser

from app import security
from app.config import Settings
from app.database import get_db_session
from app.models import TeamMembership, User
from app.schemas import (
    AccessTokenResponse,
    LoginRequest,
    PublicUser,
    RegistrationRequest,
    UserProfileResponse,
    UserProfileUpdateRequest,
)
from app.submission_storage import (
    AVATAR_EXTENSIONS,
    MAX_AVATAR_SIZE_BYTES,
    MAX_MULTIPART_OVERHEAD_BYTES,
    FileValidationError,
    PrivateStorageUnavailable,
    StagedUpload,
    delete_stored_file,
    open_stored_file,
    stage_upload,
)

logger = logging.getLogger("gradtrack.auth")
router = APIRouter(prefix="/auth", tags=["authentication"])
_bearer_scheme = HTTPBearer(auto_error=False)
_SYSTEM_ROLES = frozenset({"student", "supervisor", "coordinator"})

DbSession = Annotated[Session, Depends(get_db_session)]


class UploadRequestTooLarge(Exception):
    """The complete multipart body exceeded the bounded parser allowance."""


async def _single_avatar_upload(
    request: Request,
) -> AsyncIterator[UploadFile]:
    """Parse only one `file` part and close its temporary upload after the route."""
    content_type = request.headers.get("content-type", "")
    if not content_type.startswith("multipart/form-data"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A single multipart file named 'file' is required",
        )

    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            declared_length = int(content_length)
        except ValueError:
            declared_length = 0
        if declared_length > MAX_AVATAR_SIZE_BYTES + MAX_MULTIPART_OVERHEAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="The uploaded file exceeds the 2 MiB limit",
            )

    async def bounded_stream() -> AsyncIterator[bytes]:
        received_bytes = 0
        async for chunk in request.stream():
            received_bytes += len(chunk)
            if received_bytes > MAX_AVATAR_SIZE_BYTES + MAX_MULTIPART_OVERHEAD_BYTES:
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
            detail="The uploaded request exceeds the 2 MiB limit",
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


AvatarUpload = Annotated[UploadFile, Depends(_single_avatar_upload)]


def _file_chunks(source: BinaryIO) -> Iterator[bytes]:
    try:
        while chunk := source.read(1024 * 1024):
            yield chunk
    finally:
        source.close()


def stream_avatar(storage_key: str, configured_dir: str | None) -> StreamingResponse:
    try:
        source = open_stored_file(configured_dir, storage_key)
    except PrivateStorageUnavailable:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Avatar not found",
        ) from None

    try:
        header = source.read(8)
        file_size = source.seek(0, 2)
        source.seek(0)
    except OSError:
        source.close()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Avatar file is unavailable",
        ) from None

    if header == b"\x89PNG\r\n\x1a\n":
        media_type = "image/png"
        filename = "avatar.png"
    elif header.startswith(b"\xff\xd8\xff"):
        media_type = "image/jpeg"
        filename = "avatar.jpg"
    else:
        source.close()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Avatar file is unavailable",
        )

    headers = {
        "Content-Disposition": f'inline; filename="{filename}"',
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, no-store",
        "Content-Length": str(file_size),
    }
    return StreamingResponse(
        _file_chunks(source),
        media_type=media_type,
        headers=headers,
        background=BackgroundTask(source.close),
    )


def _credentials_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _require_auth_configuration() -> None:
    try:
        security.require_signing_key()
    except security.AuthConfigurationError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured",
        ) from None


@router.post(
    "/register",
    response_model=PublicUser,
    status_code=status.HTTP_201_CREATED,
)
def register_student(payload: RegistrationRequest, session: DbSession) -> User:
    """Create an account with the student role assigned by the server."""
    _require_auth_configuration()
    user = User(
        email=str(payload.email),
        password_hash=security.hash_password(payload.password),
        display_name=payload.display_name,
        system_role="student",
    )
    session.add(user)
    try:
        session.commit()
        session.refresh(user)
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        ) from None
    return user


@router.post("/login", response_model=AccessTokenResponse)
def login(payload: LoginRequest, session: DbSession) -> AccessTokenResponse:
    """Verify credentials and return a short-lived bearer token."""
    _require_auth_configuration()
    user = session.scalar(select(User).where(User.email == str(payload.email)))
    password_is_valid = security.verify_password(
        payload.password, user.password_hash if user is not None else None
    )
    if user is None or not user.is_active or not password_is_valid:
        raise _credentials_error()

    return AccessTokenResponse(
        access_token=security.create_access_token(user.id),
        expires_in=security.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)
    ],
    session: DbSession,
) -> User:
    """Resolve the current active account from a verified bearer token."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _credentials_error()
    try:
        user_id = security.decode_access_token(credentials.credentials)
    except security.AuthConfigurationError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured",
        ) from None
    except (InvalidTokenError, TypeError, ValueError):
        raise _credentials_error() from None

    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise _credentials_error()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("/me", response_model=UserProfileResponse)
def read_current_user(current_user: CurrentUser) -> User:
    """Return only fields approved for the authenticated account."""
    return current_user


@router.patch("/me", response_model=UserProfileResponse)
def update_profile(
    payload: UserProfileUpdateRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> User:
    """Update allowed profile details for the authenticated account."""
    fields_set = payload.model_fields_set
    if not fields_set:
        return current_user

    if "display_name" in fields_set:
        current_user.display_name = payload.display_name  # type: ignore[assignment]
    if "student_number" in fields_set:
        current_user.student_number = payload.student_number
    if "faculty" in fields_set:
        current_user.faculty = payload.faculty
    if "department" in fields_set:
        current_user.department = payload.department
    if "academic_level" in fields_set:
        current_user.academic_level = payload.academic_level
    if "bio" in fields_set:
        current_user.bio = payload.bio

    try:
        session.commit()
        session.refresh(current_user)
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile could not be updated",
        ) from None
    except SQLAlchemyError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Profile could not be updated",
        ) from None

    return current_user


@router.post(
    "/me/avatar",
    response_model=UserProfileResponse,
    status_code=status.HTTP_200_OK,
)
def upload_avatar(
    upload: AvatarUpload,
    current_user: CurrentUser,
    session: DbSession,
) -> User:
    """Stream, validate, and store a private user profile avatar."""
    configured_dir = Settings.from_environment().private_upload_dir
    staged: StagedUpload | None = None
    try:
        staged = stage_upload(
            upload.file,
            filename=upload.filename,
            content_type=upload.content_type,
            configured_dir=configured_dir,
            max_file_size_bytes=MAX_AVATAR_SIZE_BYTES,
            allowed_extensions=AVATAR_EXTENSIONS,
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

    old_storage_key = current_user.avatar_storage_key
    try:
        current_user.avatar_storage_key = staged.storage_key
        session.flush()
        staged.promote()
        session.commit()
        staged.committed = True
        session.refresh(current_user)
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Avatar could not be saved",
        ) from None
    except (SQLAlchemyError, PrivateStorageUnavailable) as error:
        session.rollback()
        logger.error(
            "Avatar persistence failed: exception=%s",
            type(error).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Avatar could not be saved",
        ) from None
    except Exception as error:
        session.rollback()
        logger.error(
            "Avatar processing failed: exception=%s",
            type(error).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Avatar could not be saved",
        ) from None
    finally:
        if staged is not None:
            staged.cleanup()

    if old_storage_key and old_storage_key != staged.storage_key:
        delete_stored_file(configured_dir, old_storage_key)

    return current_user


@router.delete(
    "/me/avatar",
    response_model=UserProfileResponse,
    status_code=status.HTTP_200_OK,
)
def delete_avatar(
    current_user: CurrentUser,
    session: DbSession,
) -> User:
    """Clear own avatar with safe, idempotent behavior."""
    old_key = current_user.avatar_storage_key
    if old_key is not None:
        current_user.avatar_storage_key = None
        try:
            session.commit()
            session.refresh(current_user)
        except SQLAlchemyError:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Avatar could not be deleted",
            ) from None
        delete_stored_file(Settings.from_environment().private_upload_dir, old_key)
    return current_user


@router.get(
    "/me/avatar",
    response_class=StreamingResponse,
    responses={
        200: {
            "content": {
                "image/png": {},
                "image/jpeg": {},
            },
            "description": "The authenticated user's profile avatar.",
        },
        404: {"description": "Avatar not found"},
        503: {"description": "Avatar file is unavailable"},
    },
)
def read_own_avatar(current_user: CurrentUser) -> StreamingResponse:
    """Stream the authenticated user's profile avatar."""
    if not current_user.avatar_storage_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Avatar not found",
        )
    return stream_avatar(
        current_user.avatar_storage_key,
        Settings.from_environment().private_upload_dir,
    )


def require_system_roles(*allowed_roles: str) -> Callable[..., User]:
    """Build a dependency that limits access to allowed system roles."""
    if not allowed_roles or not set(allowed_roles).issubset(_SYSTEM_ROLES):
        raise ValueError("At least one supported system role is required")

    def dependency(current_user: CurrentUser) -> User:
        if current_user.system_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized for this resource",
            )
        return current_user

    return dependency


def get_current_team_membership(
    team_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> TeamMembership:
    """Require and return this account's membership in the requested team."""
    membership = session.scalar(
        select(TeamMembership).where(
            TeamMembership.team_id == team_id,
            TeamMembership.user_id == current_user.id,
        )
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized for this resource",
        )
    return membership


CurrentTeamMembership = Annotated[TeamMembership, Depends(get_current_team_membership)]


def require_team_leader() -> Callable[..., TeamMembership]:
    """Build a dependency that requires leader membership in this team."""

    def dependency(membership: CurrentTeamMembership) -> TeamMembership:
        if membership.role != "leader":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized for this resource",
            )
        return membership

    return dependency
