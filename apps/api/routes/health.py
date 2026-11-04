"""Liveness and readiness.

Readiness deliberately reports a degraded state instead of raising, so an orchestrator can make
the routing decision rather than receiving an ambiguous 500.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from db import get_db
from schemas.common import HealthResponse, ReadinessResponse

router = APIRouter(tags=["health"])

VERSION = "0.1.0"


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(version=VERSION)


@router.get("/health/ready", response_model=ReadinessResponse)
def ready(db: Session = Depends(get_db)) -> ReadinessResponse:
    try:
        db.execute(text("SELECT 1"))
        database_ok = True
        detail = None
    except Exception as exc:  # noqa: BLE001 - readiness reports, it does not raise
        database_ok = False
        detail = type(exc).__name__

    return ReadinessResponse(
        status="ready" if database_ok else "degraded",
        database=database_ok,
        detail=detail,
    )
