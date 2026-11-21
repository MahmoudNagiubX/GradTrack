"""Password hashing and signed access-token operations."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from pwdlib.exceptions import PwdlibError

from app.config import Settings

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15

settings = Settings.from_environment()
_password_hasher = PasswordHash.recommended()
# Keep unknown-account login work comparable without using a real user's hash.
_DUMMY_PASSWORD_HASH = _password_hasher.hash("gradtrack-unknown-account-dummy")


class AuthConfigurationError(RuntimeError):
    """Raised when auth is used without an adequate environment secret."""


def require_signing_key() -> str:
    """Return the configured key or fail closed when it is missing or weak."""
    key = settings.auth_secret_key
    if key is None or len(key.encode("utf-8")) < 32:
        raise AuthConfigurationError("Authentication is not configured")
    return key


def hash_password(password: str) -> str:
    """Hash a password with the recommended Argon2id parameters."""
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """Verify a password without disclosing whether an account exists."""
    candidate_hash = password_hash or _DUMMY_PASSWORD_HASH
    try:
        verified = _password_hasher.verify(password, candidate_hash)
    except PwdlibError:
        verified = False
    return password_hash is not None and verified


def create_access_token(user_id: UUID) -> str:
    """Sign a short-lived token whose subject is the user's stable key."""
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "type": "access",
    }
    return jwt.encode(payload, require_signing_key(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> UUID:
    """Verify signature, algorithm, expiry, token type, and UUID subject."""
    payload = jwt.decode(
        token,
        require_signing_key(),
        algorithms=[JWT_ALGORITHM],
        options={"require": ["exp", "iat", "sub", "type"]},
    )
    if payload.get("type") != "access" or not isinstance(payload.get("sub"), str):
        raise InvalidTokenError("Invalid access token")
    try:
        return UUID(payload["sub"])
    except ValueError as error:
        raise InvalidTokenError("Invalid access token subject") from error
