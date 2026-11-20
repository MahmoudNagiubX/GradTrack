"""Manual student authentication and reusable authorization dependencies."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import security
from app.database import get_db_session
from app.models import TeamMembership, User
from app.schemas import (
    AccessTokenResponse,
    LoginRequest,
    PublicUser,
    RegistrationRequest,
)

router = APIRouter(prefix="/auth", tags=["authentication"])
_bearer_scheme = HTTPBearer(auto_error=False)
_SYSTEM_ROLES = frozenset({"student", "supervisor", "coordinator"})

DbSession = Annotated[Session, Depends(get_db_session)]


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


@router.get("/me", response_model=PublicUser)
def read_current_user(current_user: CurrentUser) -> User:
    """Return only fields approved for the authenticated account."""
    return current_user


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
