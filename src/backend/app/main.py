"""FastAPI application entry point."""

import logging

from fastapi import FastAPI, Request

from app.config import Settings

settings = Settings.from_environment()

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("gradtrack.backend")
logger.setLevel(settings.log_level)

app = FastAPI(title=settings.app_name, debug=settings.debug)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log request outcomes without recording paths, bodies, or credentials."""
    try:
        response = await call_next(request)
    except Exception as error:
        logger.error(
            "Unhandled request failure: method=%s exception=%s",
            request.method,
            type(error).__name__,
        )
        raise

    logger.info(
        "Request completed: method=%s status_code=%s",
        request.method,
        response.status_code,
    )
    return response


@app.get("/health")
def health() -> dict[str, str]:
    """Return the service health status."""
    return {"status": "ok"}
