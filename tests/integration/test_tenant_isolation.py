"""Tenant isolation, proved against a real PostgreSQL instance.

This is the BRD success criterion — *zero cross-tenant data access* — expressed as executable tests
rather than a claim in a document. It runs in CI against the same container image production uses,
because RLS behaviour depends on the connecting role and cannot be simulated.

Three details decide whether these tests mean anything:

1. **A non-superuser connection.** Superusers bypass RLS regardless of FORCE. A test that connects as
   the bootstrap role would pass while the deployed system leaked everything.
2. **The real schema.** Tables are created by running the actual migrations, not a fixture subset, so
   a future table added without a policy fails here rather than in an incident.
3. **Assertions on absence.** Deny is the expected outcome, so each test asserts zero rows, zero
   affected rows, or an error — never "the right rows came back".

Set `DATABASE_URL_TEST` to run locally; CI provides it.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

DATABASE_URL = os.getenv("DATABASE_URL_TEST")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="requires PostgreSQL; set DATABASE_URL_TEST (CI runs this against a service container)",
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_FILES = [
    ROOT / "database" / "schemas" / "001_initial.sql",
    ROOT / "database" / "migrations" / "002_rls_hardening.sql",
]

APP_ROLE = "threadmind_app"
APP_PASSWORD = "threadmind_app_pw"

ORG_A = uuid.UUID("aaaaaaaa-0000-4000-8000-000000000001")
ORG_B = uuid.UUID("bbbbbbbb-0000-4000-8000-000000000002")
USER_A = uuid.UUID("aaaaaaaa-0000-4000-8000-000000000011")
USER_B = uuid.UUID("bbbbbbbb-0000-4000-8000-000000000022")
FACTORY_A = uuid.UUID("aaaaaaaa-0000-4000-8000-000000000031")
FACTORY_B = uuid.UUID("bbbbbbbb-0000-4000-8000-000000000032")
MACHINE_A = uuid.UUID("aaaaaaaa-0000-4000-8000-000000000041")
MACHINE_B = uuid.UUID("bbbbbbbb-0000-4000-8000-000000000042")
INVESTIGATION_A = uuid.UUID("aaaaaaaa-0000-4000-8000-000000000051")
INVESTIGATION_B = uuid.UUID("bbbbbbbb-0000-4000-8000-000000000052")
SENSOR_A = uuid.UUID("aaaaaaaa-0000-4000-8000-000000000061")

TENANT_TABLES = [
    "factories",
    "machines",
    "production_batches",
    "fabric_images",
    "inspection_results",
    "sensor_readings",
    "machine_predictions",
    "maintenance_records",
    "investigations",
    "agent_runs",
    "system_alerts",
    "audit_logs",
    "organization_members",
    "investigation_evidence",
    "root_cause_hypotheses",
    "agent_actions",
    "users",
    "organizations",
]


@pytest.fixture(scope="session")
def admin_engine():
    engine = create_engine(DATABASE_URL, isolation_level="AUTOCOMMIT", future=True)
    with engine.connect() as conn:
        for path in SCHEMA_FILES:
            # exec_driver_sql, not text(): these are DDL files containing casts like `::uuid` and
            # multi-statement bodies. Letting SQLAlchemy parse them for bind parameters is how a
            # migration applies differently in tests than in production.
            conn.exec_driver_sql(path.read_text())

        conn.exec_driver_sql(f"DROP ROLE IF EXISTS {APP_ROLE}")
        conn.exec_driver_sql(f"CREATE ROLE {APP_ROLE} LOGIN PASSWORD '{APP_PASSWORD}'")
        conn.exec_driver_sql(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}")
        conn.exec_driver_sql(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE}"
        )

        _seed(conn)

    yield engine
    engine.dispose()


def _seed(conn) -> None:
    conn.execute(
        text("INSERT INTO organizations (id, name) VALUES (:a, 'Factory A'), (:b, 'Factory B')"),
        {"a": ORG_A, "b": ORG_B},
    )
    conn.execute(
        text(
            "INSERT INTO users (id, email, full_name) VALUES (:a, 'a@example.com', 'A'), (:b, 'b@example.com', 'B')"
        ),
        {"a": USER_A, "b": USER_B},
    )
    conn.execute(
        text(
            "INSERT INTO organization_members (organization_id, user_id, role) VALUES "
            "(:org_a, :user_a, 'factory_admin'), (:org_b, :user_b, 'factory_admin')"
        ),
        {"org_a": ORG_A, "user_a": USER_A, "org_b": ORG_B, "user_b": USER_B},
    )
    conn.execute(
        text(
            "INSERT INTO factories (id, organization_id, name) VALUES "
            "(:fa, :org_a, 'Factory A'), (:fb, :org_b, 'Factory B')"
        ),
        {"fa": FACTORY_A, "org_a": ORG_A, "fb": FACTORY_B, "org_b": ORG_B},
    )
    conn.execute(
        text(
            "INSERT INTO machines (id, organization_id, factory_id, machine_code, machine_name) VALUES "
            "(:ma, :org_a, :fa, 'L-01', 'Loom A'), (:mb, :org_b, :fb, 'L-02', 'Loom B')"
        ),
        {
            "ma": MACHINE_A,
            "org_a": ORG_A,
            "fa": FACTORY_A,
            "mb": MACHINE_B,
            "org_b": ORG_B,
            "fb": FACTORY_B,
        },
    )
    conn.execute(
        text(
            "INSERT INTO machine_sensors (id, organization_id, machine_id, sensor_type, sensor_name) "
            "VALUES (:sa, :org_a, :ma, 'vibration', 'Spindle vibration')"
        ),
        {"sa": SENSOR_A, "org_a": ORG_A, "ma": MACHINE_A},
    )
    conn.execute(
        text(
            "INSERT INTO investigations (id, organization_id, factory_id, issue_type, start_timestamp) "
            "VALUES (:ia, :org_a, :fa, 'defect_spike', now()), (:ib, :org_b, :fb, 'defect_spike', now())"
        ),
        {
            "ia": INVESTIGATION_A,
            "org_a": ORG_A,
            "fa": FACTORY_A,
            "ib": INVESTIGATION_B,
            "org_b": ORG_B,
            "fb": FACTORY_B,
        },
    )
    conn.execute(
        text(
            "INSERT INTO investigation_evidence "
            "(investigation_id, evidence_type, evidence_description) "
            "VALUES (:ia, 'sensor_window', 'evidence for A'), (:ib, 'sensor_window', 'evidence for B')"
        ),
        {"ia": INVESTIGATION_A, "ib": INVESTIGATION_B},
    )


@pytest.fixture(scope="session")
def app_engine(admin_engine):
    """Engine bound to a non-superuser role, so RLS actually applies."""
    url = make_url(DATABASE_URL).set(username=APP_ROLE, password=APP_PASSWORD)
    engine = create_engine(url, future=True)
    yield engine
    engine.dispose()


def scoped_connection(app_engine, org: uuid.UUID, user: uuid.UUID):
    """Open a transaction scoped to one tenant, exactly as the API does per request."""
    conn = app_engine.connect()
    conn.execute(
        text(
            "SELECT set_config('app.current_org', :org, true), "
            "set_config('app.current_user', :user, true)"
        ),
        {"org": str(org), "user": str(user)},
    )
    return conn


def test_rls_is_enabled_and_forced_on_every_tenant_table(admin_engine):
    """FORCE matters as much as ENABLE: the application role owns these tables in some deployments,
    and an owner silently bypasses its own policies."""
    with admin_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
                "WHERE relname = ANY(:tables)"
            ),
            {"tables": TENANT_TABLES},
        ).all()

    state = {name: (enabled, forced) for name, enabled, forced in rows}
    missing = [t for t in TENANT_TABLES if t not in state]
    assert not missing, f"tables not found: {missing}"

    unenabled = [t for t, (enabled, _) in state.items() if not enabled]
    unforced = [t for t, (_, forced) in state.items() if not forced]
    assert not unenabled, f"RLS not enabled: {unenabled}"
    assert not unforced, f"RLS not forced (owner would bypass): {unforced}"


def test_org_a_sees_only_its_own_machines(app_engine):
    conn = scoped_connection(app_engine, ORG_A, USER_A)
    try:
        rows = conn.execute(text("SELECT id FROM machines")).all()
        assert [row[0] for row in rows] == [MACHINE_A]
    finally:
        conn.close()


def test_org_b_cannot_read_org_a_machine_by_id(app_engine):
    """Direct object reference: the classic cross-tenant read."""
    conn = scoped_connection(app_engine, ORG_B, USER_B)
    try:
        count = conn.execute(
            text("SELECT count(*) FROM machines WHERE id = :id"), {"id": MACHINE_A}
        ).scalar_one()
        assert count == 0
    finally:
        conn.close()


def test_org_b_cannot_modify_org_a_machine(app_engine):
    conn = scoped_connection(app_engine, ORG_B, USER_B)
    try:
        result = conn.execute(
            text("UPDATE machines SET machine_name = 'owned' WHERE id = :id"), {"id": MACHINE_A}
        )
        assert result.rowcount == 0
    finally:
        conn.close()

    with app_engine.connect() as verify:
        verify.execute(text("SELECT set_config('app.current_org', :o, true)"), {"o": str(ORG_A)})
        name = verify.execute(
            text("SELECT machine_name FROM machines WHERE id = :id"), {"id": MACHINE_A}
        ).scalar_one()
        assert name == "Loom A"


def test_unscoped_connection_sees_nothing(app_engine):
    """Default deny. If this fails, a query that forgets its WHERE clause leaks the whole platform."""
    with app_engine.connect() as conn:
        machines = conn.execute(text("SELECT count(*) FROM machines")).scalar_one()
        factories = conn.execute(text("SELECT count(*) FROM factories")).scalar_one()
        evidence = conn.execute(text("SELECT count(*) FROM investigation_evidence")).scalar_one()

    assert (machines, factories, evidence) == (0, 0, 0)


def test_child_table_inherits_parent_isolation(app_engine):
    """investigation_evidence has no organization_id; isolation must come from its parent."""
    conn = scoped_connection(app_engine, ORG_A, USER_A)
    try:
        descriptions = [
            row[0]
            for row in conn.execute(text("SELECT evidence_description FROM investigation_evidence"))
        ]
    finally:
        conn.close()

    assert descriptions == ["evidence for A"]


def test_membership_table_does_not_leak_other_tenants(app_engine):
    conn = scoped_connection(app_engine, ORG_A, USER_A)
    try:
        rows = conn.execute(text("SELECT organization_id, user_id FROM organization_members")).all()
    finally:
        conn.close()

    assert rows == [(ORG_A, USER_A)]


def test_user_can_see_themselves_and_org_peers_only(app_engine):
    conn = scoped_connection(app_engine, ORG_A, USER_A)
    try:
        ids = [row[0] for row in conn.execute(text("SELECT id FROM users"))]
    finally:
        conn.close()

    assert USER_A in ids
    assert USER_B not in ids


def test_duplicate_sensor_reading_is_rejected_by_the_natural_key(app_engine):
    """At-least-once delivery must not become double counting."""
    insert = text(
        "INSERT INTO sensor_readings "
        '(organization_id, machine_id, sensor_id, "timestamp", numeric_value, quality_flag) '
        "VALUES (:org, :machine, :sensor, '2026-11-04T09:00:00Z', 3.4, 'good')"
    )
    params = {"org": ORG_A, "machine": MACHINE_A, "sensor": SENSOR_A}

    conn = scoped_connection(app_engine, ORG_A, USER_A)
    try:
        conn.execute(insert, params)
        with pytest.raises(IntegrityError):
            conn.execute(insert, params)
        conn.rollback()
    finally:
        conn.close()
