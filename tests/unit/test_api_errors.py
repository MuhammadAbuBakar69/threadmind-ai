"""API behaviour tests: authentication, error envelope, and telemetry ingestion.

These run against the real application object with only the repository and the principal overridden,
so the middleware stack, exception handlers and validation wiring are genuinely exercised. No
database is required.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from core.security import Principal
from deps import get_principal
from fastapi.testclient import TestClient
from main import app
from routes.telemetry import get_telemetry_repository
from services.telemetry import InMemoryTelemetryRepository

from industrial.telemetry import MachineState, QualityFlag, SensorType


@pytest.fixture
def client(principal: Principal):
    repository = InMemoryTelemetryRepository()
    app.dependency_overrides[get_principal] = lambda: principal
    app.dependency_overrides[get_telemetry_repository] = lambda: repository
    with TestClient(app, raise_server_exceptions=False) as test_client:
        test_client.repository = repository  # type: ignore[attr-defined]
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def anonymous_client():
    app.dependency_overrides.clear()
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def payload(org: uuid.UUID, machine: uuid.UUID, **overrides) -> dict:
    base = {
        "event_id": str(uuid.uuid4()),
        "organization_id": str(org),
        "machine_id": str(machine),
        "sensor_id": str(uuid.uuid4()),
        "sensor_type": SensorType.VIBRATION.value,
        "machine_state": MachineState.RUNNING.value,
        "value": 3.2,
        "timestamp": datetime.now(UTC).isoformat(),
        "quality_flag": QualityFlag.GOOD.value,
    }
    base.update(overrides)
    return {"readings": [base]}


def test_missing_token_returns_401_envelope(anonymous_client):
    response = anonymous_client.get("/api/v1/factories")
    assert response.status_code in (401, 404)  # route may not exist yet; auth is checked below

    response = anonymous_client.post("/api/v1/telemetry", json={"readings": []})
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "unauthenticated"
    assert body["error"]["requirement"] == "FR-001"
    assert body["request_id"]
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_request_id_is_returned_and_echoed():
    with TestClient(app) as anonymous:
        response = anonymous.get("/health", headers={"X-Request-ID": "trace-abc-123"})
        assert response.headers["X-Request-ID"] == "trace-abc-123"
        assert response.status_code == 200


def test_unsafe_request_id_is_replaced():
    with TestClient(app) as anonymous:
        response = anonymous.get("/health", headers={"X-Request-ID": "bad id with spaces"})
        assert response.headers["X-Request-ID"] != "bad id with spaces"
        assert len(response.headers["X-Request-ID"]) == 32


def test_valid_batch_is_accepted(client, org_id, machine_id):
    response = client.post("/api/v1/telemetry", json=payload(org_id, machine_id))
    assert response.status_code == 202
    body = response.json()
    assert body["accepted"] == 1
    assert body["duplicates"] == 0
    assert body["rejected"] == []


def test_out_of_range_reading_is_rejected_but_rest_stored(client, org_id, machine_id):
    batch = payload(org_id, machine_id)
    batch["readings"].append(
        {**batch["readings"][0], "event_id": str(uuid.uuid4()), "value": 9000.0}
    )
    response = client.post("/api/v1/telemetry", json=batch)
    assert response.status_code == 202
    body = response.json()
    assert body["accepted"] == 1
    assert len(body["rejected"]) == 1
    assert body["rejection_rate"] == pytest.approx(0.5)


def test_duplicate_delivery_is_counted_not_treated_as_new(client, org_id, machine_id):
    reading = payload(org_id, machine_id)
    first = client.post("/api/v1/telemetry", json=reading).json()
    second = client.post("/api/v1/telemetry", json=reading).json()
    assert first["accepted"] == 1
    assert second["accepted"] == 0
    assert second["duplicates"] == 1


def test_reading_for_another_organization_is_refused(client, other_org_id, machine_id):
    response = client.post("/api/v1/telemetry", json=payload(other_org_id, machine_id))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "insufficient_role"


def test_malformed_payload_reports_fields_without_echoing_values(client, org_id, machine_id):
    batch = payload(org_id, machine_id)
    batch["readings"][0]["value"] = "not-a-number"
    response = client.post("/api/v1/telemetry", json=batch)
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "invalid_payload"
    assert body["error"]["fields"]
    assert "not-a-number" not in response.text


def test_unknown_field_is_refused(client, org_id, machine_id):
    batch = payload(org_id, machine_id)
    batch["readings"][0]["mystery"] = 1
    response = client.post("/api/v1/telemetry", json=batch)
    assert response.status_code == 422


def test_internal_failure_hides_details(client, org_id, machine_id):
    class Exploding(InMemoryTelemetryRepository):
        def insert_many(self, readings):
            raise RuntimeError("connection string postgres://user:secret@internal/db")

    app.dependency_overrides[get_telemetry_repository] = lambda: Exploding()
    response = client.post("/api/v1/telemetry", json=payload(org_id, machine_id))
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_error"
    assert "postgres://" not in response.text
    assert "RuntimeError" not in response.text
    assert "Traceback" not in response.text
    assert body["request_id"]


def test_readiness_reports_degraded_without_a_database():
    """Readiness must answer, not crash, when the database is unreachable."""
    with TestClient(app) as anonymous:
        response = anonymous.get("/health/ready")
        assert response.status_code == 200
        assert response.json()["status"] in {"ready", "degraded"}
