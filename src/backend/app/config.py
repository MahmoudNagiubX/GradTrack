"""Environment-based configuration for the GradTrack API."""

import logging
import os
from dataclasses import dataclass, field

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

_LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}
_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}
_DEFAULT_APP_NAME = "GradTrack API"
_DEFAULT_DATABASE_URL = (
    "postgresql+psycopg://gradtrack:gradtrack@127.0.0.1:5432/gradtrack_dev"
)


@dataclass(frozen=True, slots=True)
class Settings:
    """Small set of settings needed by the GradTrack API."""

    app_name: str = _DEFAULT_APP_NAME
    debug: bool = False
    log_level: int = logging.INFO
    database_url: str = _DEFAULT_DATABASE_URL
    auth_secret_key: str | None = field(default=None, repr=False)
    private_upload_dir: str | None = field(default=None, repr=False)

    @classmethod
    def from_environment(cls) -> "Settings":
        """Read settings from environment variables, using safe defaults."""
        app_name = os.getenv("GRADTRACK_APP_NAME", _DEFAULT_APP_NAME).strip()
        if not app_name:
            raise ValueError("GRADTRACK_APP_NAME must not be empty")

        debug_value = os.getenv("GRADTRACK_DEBUG", "false").strip().lower()
        if debug_value in _TRUE_VALUES:
            debug = True
        elif debug_value in _FALSE_VALUES:
            debug = False
        else:
            raise ValueError("GRADTRACK_DEBUG must be a boolean value")

        log_level_name = os.getenv("GRADTRACK_LOG_LEVEL", "INFO").strip().upper()
        try:
            log_level = _LOG_LEVELS[log_level_name]
        except KeyError:
            allowed_levels = ", ".join(_LOG_LEVELS)
            raise ValueError(
                f"GRADTRACK_LOG_LEVEL must be one of: {allowed_levels}"
            ) from None

        database_url = os.getenv(
            "GRADTRACK_DATABASE_URL", _DEFAULT_DATABASE_URL
        ).strip()
        try:
            parsed_database_url = make_url(database_url)
        except ArgumentError:
            raise ValueError("GRADTRACK_DATABASE_URL must be a valid URL") from None
        if (
            not database_url
            or parsed_database_url.drivername != "postgresql+psycopg"
            or not parsed_database_url.database
        ):
            raise ValueError(
                "GRADTRACK_DATABASE_URL must use postgresql+psycopg and "
                "include a database name"
            )

        auth_secret_key = os.getenv("GRADTRACK_AUTH_SECRET_KEY")
        if auth_secret_key is not None:
            auth_secret_key = auth_secret_key.strip()
            if not auth_secret_key:
                raise ValueError("GRADTRACK_AUTH_SECRET_KEY must not be empty")

        private_upload_dir = os.getenv("GRADTRACK_PRIVATE_UPLOAD_DIR") or None

        return cls(
            app_name=app_name,
            debug=debug,
            log_level=log_level,
            database_url=database_url,
            auth_secret_key=auth_secret_key,
            private_upload_dir=private_upload_dir,
        )
