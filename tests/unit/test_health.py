"""Liveness must not depend on the database; readiness must."""

from fastapi.testclient import TestClient
from main import app


def test_liveness_is_independent_of_the_database():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_root_declares_the_scope_boundary():
    client = TestClient(app)
    body = client.get("/").json()
    assert "no machine control" in body["scope"]
