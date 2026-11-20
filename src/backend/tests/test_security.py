"""Database-independent tests for password hashing and access-token signing."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from app import security
from app.schemas import LoginRequest, RegistrationRequest
from pydantic import ValidationError


def _credential_payload(schema: type, password: str) -> dict[str, str]:
    payload = {"email": "student@example.com", "password": password}
    if schema is RegistrationRequest:
        payload["display_name"] = "Synthetic Student"
    return payload


@pytest.mark.parametrize("schema", (RegistrationRequest, LoginRequest))
def test_password_policy_rejects_15_characters(schema: type) -> None:
    with pytest.raises(ValidationError):
        schema.model_validate(_credential_payload(schema, "x" * 15))


@pytest.mark.parametrize("schema", (RegistrationRequest, LoginRequest))
def test_password_policy_accepts_16_characters_without_complexity_rules(
    schema: type,
) -> None:
    password = "x" * 16

    credentials = schema.model_validate(_credential_payload(schema, password))

    assert credentials.password == password


@pytest.mark.parametrize("schema", (RegistrationRequest, LoginRequest))
def test_password_policy_preserves_long_unicode_passphrases_and_spaces(
    schema: type,
) -> None:
    password = f"  {'あいことば ' * 11}  "
    assert len(password) >= 64

    credentials = schema.model_validate(_credential_payload(schema, password))

    assert credentials.password == password


def test_password_hash_verification_preserves_unicode_and_whitespace() -> None:
    password = f"  {'あいことば ' * 11}  "
    password_hash = security.hash_password(password)

    assert security.verify_password(password, password_hash)
    assert not security.verify_password(password.strip(), password_hash)


def test_passwords_use_argon2_and_never_verify_plaintext() -> None:
    password = "Synthetic!Passphrase2026"
    password_hash = security.hash_password(password)

    assert password_hash.startswith("$argon2id$")
    assert password_hash != password
    assert security.verify_password(password, password_hash)
    assert not security.verify_password("Different!Passphrase2026", password_hash)
    assert not security.verify_password(password, None)


def test_access_token_is_signed_and_contains_the_user_subject() -> None:
    user_id = uuid4()

    token = security.create_access_token(user_id)

    assert security.decode_access_token(token) == user_id


def test_access_token_expiration_is_verified() -> None:
    now = datetime.now(UTC)
    expired_token = jwt.encode(
        {
            "sub": str(uuid4()),
            "iat": now - timedelta(minutes=2),
            "exp": now - timedelta(minutes=1),
            "type": "access",
        },
        security.settings.auth_secret_key,
        algorithm=security.JWT_ALGORITHM,
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        security.decode_access_token(expired_token)


def test_access_token_rejects_an_unconfigured_algorithm() -> None:
    token = jwt.encode(
        {"sub": str(uuid4())},
        security.settings.auth_secret_key,
        algorithm="HS384",
    )

    with pytest.raises(jwt.InvalidAlgorithmError):
        security.decode_access_token(token)


@pytest.mark.parametrize("secret", (None, "too-short"))
def test_signing_requires_a_configured_32_byte_key(
    monkeypatch: pytest.MonkeyPatch, secret: str | None
) -> None:
    monkeypatch.setattr(
        security,
        "settings",
        replace(security.settings, auth_secret_key=secret),
    )

    with pytest.raises(security.AuthConfigurationError):
        security.require_signing_key()
