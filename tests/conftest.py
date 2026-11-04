"""Shared test fixtures.

The suite deliberately runs without a database. Route tests inject a fake repository through
FastAPI's dependency overrides, so the validation, authentication and error paths are all exercised
in CI even when no Postgres is available. The tests that genuinely need a database live in
`tests/integration` and skip themselves explicitly when `DATABASE_URL_TEST` is absent.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from core.security import Principal


@pytest.fixture
def org_id() -> uuid.UUID:
    return uuid.UUID("11111111-1111-4111-8111-111111111111")


@pytest.fixture
def other_org_id() -> uuid.UUID:
    return uuid.UUID("99999999-9999-4999-8999-999999999999")


@pytest.fixture
def machine_id() -> uuid.UUID:
    return uuid.UUID("22222222-2222-4222-8222-222222222222")


@pytest.fixture
def principal(org_id: uuid.UUID) -> Principal:
    return Principal(
        user_id=uuid.UUID("33333333-3333-4333-8333-333333333333"),
        organization_id=org_id,
        role="factory_manager",
    )


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 11, 4, 9, 30, tzinfo=UTC)


@pytest.fixture
def recent(now: datetime) -> datetime:
    return now - timedelta(minutes=1)
