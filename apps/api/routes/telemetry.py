"""Telemetry ingestion endpoints.

MQTT is the primary path for machine data; this HTTP endpoint exists for gateways that cannot hold a
broker session, and for the simulator to exercise the identical validation path.
"""

from __future__ import annotations

from core.security import Principal
from deps import get_tenant_db, require_role
from fastapi import APIRouter, Depends
from schemas.telemetry import IngestResponse, RejectionDetail
from services.telemetry import SqlTelemetryRepository, TelemetryRepository, ingest
from sqlalchemy.orm import Session

from industrial.telemetry import TelemetryBatch

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


def get_telemetry_repository(db: Session = Depends(get_tenant_db)) -> TelemetryRepository:
    """Injected so tests can exercise the route without a database.

    A route that can only be tested against a live Postgres tends to go untested.
    """
    return SqlTelemetryRepository(db)


@router.post(
    "",
    response_model=IngestResponse,
    status_code=202,
    summary="Ingest a batch of sensor readings",
)
def ingest_telemetry(
    batch: TelemetryBatch,
    principal: Principal = Depends(require_role("production_supervisor")),
    repository: TelemetryRepository = Depends(get_telemetry_repository),
) -> IngestResponse:
    """Validate and store readings (FR-022, FR-023).

    Returns 202: acceptance means the readings were validated and written, not that downstream
    anomaly scoring has run. That work is asynchronous by design.
    """
    for reading in batch.readings:
        # Tenant scope comes from the token. A reading tagged with another organization is a
        # forgery attempt or a misconfigured gateway; either way it must not be stored.
        if reading.organization_id != principal.organization_id:
            from core.errors import Forbidden

            raise Forbidden("Readings may only be submitted for your own organization.")

    result = ingest(batch.readings, repository)
    return IngestResponse(
        accepted=result.accepted,
        duplicates=result.duplicates,
        rejected=[RejectionDetail(**item) for item in result.rejected],
        rejection_rate=round(result.rejection_rate, 4),
    )
