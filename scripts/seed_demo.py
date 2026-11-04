"""Create a demo tenant so the platform is usable the moment it starts.

`docker compose up` gives you a database with a schema and no rows. A dashboard pointed at that shows
nothing, and an inspection needs a machine to attach to (FR-020). This seeds one organization, one
factory, one production line and two machines, with fixed UUIDs so repeated runs are idempotent and
documentation can reference them.

Run after the API container is healthy:

    docker compose exec api python /app/../scripts/seed_demo.py    # or: python scripts/seed_demo.py

It refuses to invent a Clerk account. Link your own with scripts/link_clerk_identity.py (see
docs/authentication.md); the seeded tenant is otherwise only reachable by the dev token issuer.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))

from db import get_sessionmaker  # noqa: E402
from sqlalchemy import text  # noqa: E402

ORG = "11111111-1111-4111-8111-111111111111"
USER = "11111111-1111-4111-8111-111111111112"
FACTORY = "11111111-1111-4111-8111-111111111113"
LINE = "11111111-1111-4111-8111-111111111114"
MACHINE_LOOM = "11111111-1111-4111-8111-111111111115"
MACHINE_KNIT = "11111111-1111-4111-8111-111111111116"
BATCH = "11111111-1111-4111-8111-111111111117"

STATEMENTS: list[tuple[str, dict]] = [
    (
        "INSERT INTO organizations (id, name, industry) VALUES (:id, 'Demo Textile Mills', 'textile') "
        "ON CONFLICT (id) DO NOTHING",
        {"id": ORG},
    ),
    (
        "INSERT INTO users (id, email, full_name) VALUES (:id, 'demo@threadmind.local', 'Demo Inspector') "
        "ON CONFLICT (id) DO NOTHING",
        {"id": USER},
    ),
    (
        "INSERT INTO organization_members (organization_id, user_id, role) "
        "VALUES (:org, :user, 'factory_admin') ON CONFLICT (organization_id, user_id) DO NOTHING",
        {"org": ORG, "user": USER},
    ),
    (
        "INSERT INTO factories (id, organization_id, name, location) "
        "VALUES (:id, :org, 'Karachi Unit 1', 'Karachi, PK') ON CONFLICT (id) DO NOTHING",
        {"id": FACTORY, "org": ORG},
    ),
    (
        "INSERT INTO production_lines (id, organization_id, factory_id, name, production_type) "
        "VALUES (:id, :org, :factory, 'Weaving Line 01', 'weaving') ON CONFLICT (id) DO NOTHING",
        {"id": LINE, "org": ORG, "factory": FACTORY},
    ),
    (
        "INSERT INTO machines (id, organization_id, factory_id, production_line_id, machine_code, "
        "machine_name, machine_type, manufacturer) VALUES "
        "(:id, :org, :factory, :line, 'L-01', 'Loom 01', 'rapier_loom', 'Picanol'), "
        "(:id2, :org, :factory, :line, 'K-01', 'Knitter 01', 'circular_knitting', 'Mayer & Cie') "
        "ON CONFLICT (id) DO NOTHING",
        {"id": MACHINE_LOOM, "id2": MACHINE_KNIT, "org": ORG, "factory": FACTORY, "line": LINE},
    ),
    (
        "INSERT INTO production_batches (id, organization_id, factory_id, production_line_id, "
        "batch_code, fabric_type, status) VALUES (:id, :org, :factory, :line, 'B-2026-001', "
        "'cotton_poplin', 'running') ON CONFLICT (organization_id, batch_code) DO NOTHING",
        {"id": BATCH, "org": ORG, "factory": FACTORY, "line": LINE},
    ),
    (
        "INSERT INTO machine_sensors (organization_id, machine_id, sensor_type, sensor_name, "
        "measurement_unit, sampling_interval) VALUES (:org, :machine, 'vibration', "
        "'Spindle vibration', 'mm/s', 1) ON CONFLICT DO NOTHING",
        {"org": ORG, "machine": MACHINE_LOOM},
    ),
]


def main() -> int:
    session = get_sessionmaker()()
    try:
        for statement, params in STATEMENTS:
            session.execute(text(statement), params)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    print("Demo tenant ready.")
    print(f"  organization  {ORG}  Demo Textile Mills")
    print(f"  factory       {FACTORY}  Karachi Unit 1")
    print(f"  machines      {MACHINE_LOOM} (Loom 01), {MACHINE_KNIT} (Knitter 01)")
    print(f"  batch         {BATCH}  B-2026-001 cotton_poplin")
    print("\nNext: link your Clerk account -> python scripts/link_clerk_identity.py --help")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
