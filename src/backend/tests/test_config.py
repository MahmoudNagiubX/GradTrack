import logging

import pytest
from app.config import Settings


def test_settings_use_safe_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "GRADTRACK_APP_NAME",
        "GRADTRACK_DEBUG",
        "GRADTRACK_LOG_LEVEL",
        "GRADTRACK_DATABASE_URL",
        "GRADTRACK_AUTH_SECRET_KEY",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = Settings.from_environment()

    assert settings.app_name == "GradTrack API"
    assert settings.debug is False
    assert settings.log_level == logging.INFO
    assert settings.database_url == (
        "postgresql+psycopg://gradtrack:gradtrack@127.0.0.1:5432/gradtrack_dev"
    )
    assert settings.auth_secret_key is None


def test_settings_read_environment_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GRADTRACK_APP_NAME", "GradTrack Development API")
    monkeypatch.setenv("GRADTRACK_DEBUG", "true")
    monkeypatch.setenv("GRADTRACK_LOG_LEVEL", "debug")
    monkeypatch.setenv(
        "GRADTRACK_AUTH_SECRET_KEY",
        "synthetic-only-gradtrack-auth-test-key-32-bytes-minimum",
    )

    settings = Settings.from_environment()

    assert settings.app_name == "GradTrack Development API"
    assert settings.debug is True
    assert settings.log_level == logging.DEBUG
    assert settings.auth_secret_key == (
        "synthetic-only-gradtrack-auth-test-key-32-bytes-minimum"
    )


@pytest.mark.parametrize(
    ("name", "value"),
    (("GRADTRACK_DEBUG", "sometimes"), ("GRADTRACK_LOG_LEVEL", "verbose")),
)
def test_settings_reject_invalid_environment_values(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValueError):
        Settings.from_environment()


def test_settings_reject_non_postgresql_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GRADTRACK_DATABASE_URL", "sqlite:///gradtrack.db")

    with pytest.raises(ValueError, match=r"postgresql\+psycopg"):
        Settings.from_environment()


def test_settings_reject_blank_auth_signing_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GRADTRACK_AUTH_SECRET_KEY", "   ")

    with pytest.raises(ValueError, match="must not be empty"):
        Settings.from_environment()


def test_settings_repr_does_not_expose_auth_signing_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "synthetic-only-gradtrack-auth-test-key-32-bytes-minimum"
    monkeypatch.setenv("GRADTRACK_AUTH_SECRET_KEY", secret)

    assert secret not in repr(Settings.from_environment())
