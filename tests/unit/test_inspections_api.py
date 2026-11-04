"""Inspection endpoint tests without a database.

`get_tenant_db` is overridden with a recording fake, so the route's wiring — authentication, content
type, size limit, storage, response shape — is exercised for real while persistence stays a stub. The
SQL itself is covered by the tenant-isolation suite against real PostgreSQL.
"""

from __future__ import annotations

import io
from uuid import uuid4

import numpy as np
import pytest
from core.config import Settings
from core.security import Principal
from deps import get_principal, get_tenant_db
from fastapi.testclient import TestClient
from main import app
from PIL import Image


def fabric_with_hole() -> bytes:
    rng = np.random.default_rng(5)
    image = np.full((256, 256), 128.0)
    image += ((np.indices((256, 256)).sum(0) % 4) - 1.5) * 3.0
    image += rng.normal(0.0, 2.0, (256, 256))
    image[100:120, 150:170] = 25.0
    buffer = io.BytesIO()
    Image.fromarray(np.clip(image, 0, 255).astype("uint8")).save(buffer, format="PNG")
    return buffer.getvalue()


class _Result:
    def __init__(self, value):
        self._value = value

    def scalar_one(self):
        return self._value

    def first(self):
        return None

    def all(self):
        return []


class RecordingSession:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []
        self.image_id = uuid4()
        self.result_id = uuid4()

    def execute(self, statement, params=None):
        sql = str(statement)
        self.calls.append((sql, params or {}))
        if "INSERT INTO fabric_images" in sql:
            return _Result(self.image_id)
        if "INSERT INTO inspection_results" in sql:
            return _Result(self.result_id)
        return _Result(None)


@pytest.fixture
def client(tmp_path, monkeypatch):
    session = RecordingSession()

    def settings():
        return Settings(vision_upload_dir=str(tmp_path))

    monkeypatch.setattr("routes.inspections.get_settings", settings)

    # One principal for the whole fixture: a fresh organization id per request would put each upload
    # in its own directory, which would hide a broken dedupe path behind a passing test.
    principal = Principal(user_id=uuid4(), organization_id=uuid4(), role="quality_inspector")
    app.dependency_overrides[get_principal] = lambda: principal
    app.dependency_overrides[get_tenant_db] = lambda: session

    with TestClient(app) as test_client:
        test_client.session = session  # type: ignore[attr-defined]
        test_client.upload_dir = tmp_path  # type: ignore[attr-defined]
        yield test_client

    app.dependency_overrides.clear()


def test_an_unauthenticated_inspection_is_rejected(tmp_path, monkeypatch):
    """No override here: the bearer dependency must be what stops an anonymous upload."""
    monkeypatch.setattr(
        "routes.inspections.get_settings", lambda: Settings(vision_upload_dir=str(tmp_path))
    )
    with TestClient(app) as raw_client:
        response = raw_client.post(
            "/api/v1/inspections", content=fabric_with_hole(), headers={"content-type": "image/png"}
        )

    assert response.status_code == 401
    assert "error" in response.json()


def test_the_content_type_must_be_an_image(client):
    response = client.post(
        "/api/v1/inspections", content=b"{}", headers={"content-type": "application/json"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["requirement"] == "FR-013"


def test_an_empty_body_is_rejected(client):
    response = client.post(
        "/api/v1/inspections", content=b"", headers={"content-type": "image/png"}
    )
    assert response.status_code == 422


def test_an_oversized_upload_is_refused_before_decoding(client, monkeypatch):
    monkeypatch.setattr(
        "routes.inspections.get_settings",
        lambda: Settings(vision_upload_dir=str(client.upload_dir), vision_max_upload_bytes=64),
    )

    response = client.post(
        "/api/v1/inspections", content=b"x" * 128, headers={"content-type": "image/png"}
    )

    assert response.status_code == 413
    # Refused before any image decode or database write.
    assert client.session.calls == []


def test_a_valid_image_is_inspected_and_persisted(client):
    response = client.post(
        "/api/v1/inspections",
        content=fabric_with_hole(),
        headers={"content-type": "image/png"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["overall_status"] == "fail"
    assert body["detector_kind"] == "baseline_untrained"
    assert body["defects"][0]["defect_class"] == "dark_region"
    assert body["width"] == 256 and body["height"] == 256

    statements = [sql for sql, _ in client.session.calls]
    assert any("fabric_images" in sql for sql in statements)
    assert any("inspection_results" in sql for sql in statements)
    assert any("detected_defects" in sql for sql in statements)


def test_the_image_is_written_under_its_content_hash(client):
    payload = fabric_with_hole()
    client.post("/api/v1/inspections", content=payload, headers={"content-type": "image/png"})

    files = list(client.upload_dir.rglob("*.bin"))
    assert len(files) == 1
    assert files[0].read_bytes() == payload
    # No half-written staging file left behind.
    assert not list(client.upload_dir.rglob("*.part"))


def test_a_duplicate_upload_reuses_the_stored_file(client):
    payload = fabric_with_hole()
    client.post("/api/v1/inspections", content=payload, headers={"content-type": "image/png"})
    client.post("/api/v1/inspections", content=payload, headers={"content-type": "image/png"})

    # Dedupe is per organization by design: two tenants that upload the same bytes get their own
    # copy, because a shared path would leak the existence of another tenant's image.
    assert len(list(client.upload_dir.rglob("*.bin"))) == 1


def test_a_corrupt_image_is_rejected_with_422(client):
    response = client.post(
        "/api/v1/inspections", content=b"not-an-image", headers={"content-type": "image/png"}
    )

    assert response.status_code == 422
    assert client.session.calls == []


def test_an_unknown_inspection_is_404_not_403(client):
    response = client.get(f"/api/v1/inspections/{uuid4()}")
    assert response.status_code == 404
