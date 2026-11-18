"""Environment-based configuration for the GradTrack API."""

import logging
import os
from dataclasses import dataclass

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


@dataclass(frozen=True, slots=True)
class Settings:
    """Small set of settings needed by the Phase 0 API."""

    app_name: str = _DEFAULT_APP_NAME
    debug: bool = False
    log_level: int = logging.INFO

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

        return cls(app_name=app_name, debug=debug, log_level=log_level)
