"""Liveness and readiness.

Readiness answers rather than raising. An orchestrator needs a decision, and a 500 from a readiness
probe is ambiguous: it could be a crashed worker or a slow database. It also must not depend on a
database session being constructible — that dependency would fail before the `try` and turn a
degraded state into an exception, which is exactly what this test caught.
"""

from core.config import get_settings
from db import get_sessionmaker
from fastapi import APIRouter
from schemas.common import HealthResponse, ReadinessResponse
from sqlalchemy import text

router = APIRouter(tags=["health"])

VERSION = "0.1.0"


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(version=VERSION)


@router.get("/health/ready", response_model=ReadinessResponse)
def ready() -> ReadinessResponse:
    database_ok = False
    detail: str | None = None

    try:
        session = get_sessionmaker()()
    except Exception as exc:  # noqa: BLE001 - driver missing, pool exhausted, config invalid
        # Report the category, never the connection string or driver internals.
        detail = f"session_unavailable:{type(exc).__name__}"
    else:
        try:
            session.execute(text("SELECT 1"))
            database_ok = True
        except Exception as exc:  # noqa: BLE001
            detail = f"database_unreachable:{type(exc).__name__}"
        finally:
            session.close()

    return ReadinessResponse(
        status="ready" if database_ok else "degraded",
        database=database_ok,
        detail=detail,
        environment=get_settings().app_env,
    )
