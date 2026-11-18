import logging

import pytest
from app.config import Settings


def test_settings_use_safe_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "GRADTRACK_APP_NAME",
        "GRADTRACK_DEBUG",
        "GRADTRACK_LOG_LEVEL",
        "GRADTRACK_DATABASE_URL",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = Settings.from_environment()

    assert settings.app_name == "GradTrack API"
    assert settings.debug is False
    assert settings.log_level == logging.INFO
    assert settings.database_url == (
        "postgresql+psycopg://gradtrack:gradtrack@127.0.0.1:5432/gradtrack_dev"
    )


def test_settings_read_environment_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GRADTRACK_APP_NAME", "GradTrack Development API")
    monkeypatch.setenv("GRADTRACK_DEBUG", "true")
    monkeypatch.setenv("GRADTRACK_LOG_LEVEL", "debug")

    settings = Settings.from_environment()

    assert settings.app_name == "GradTrack Development API"
    assert settings.debug is True
    assert settings.log_level == logging.DEBUG


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
