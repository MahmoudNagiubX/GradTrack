"""FastAPI application entry point."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from sqlalchemy.exc import SQLAlchemyError

from app.config import Settings
from app.database import check_database_connection, engine

settings = Settings.from_environment()

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("gradtrack.backend")
logger.setLevel(settings.log_level)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Dispose of the database pool during application shutdown."""
    try:
        yield
    finally:
        engine.dispose()


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)


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


@app.get("/health/database")
def database_health() -> dict[str, str]:
    """Check database connectivity separately from process health."""
    try:
        check_database_connection()
    except SQLAlchemyError as error:
        logger.error(
            "Database health check failed: exception=%s",
            type(error).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from None

    return {"status": "ok"}
