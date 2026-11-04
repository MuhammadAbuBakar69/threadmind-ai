# Database Design

## 1. Strategy

PostgreSQL is the primary relational store. High-volume sensor readings use a time-series
extension (TimescaleDB) or an equivalent strategy. Fabric images, videos, reports and model
artifacts live in object storage; the database holds only keys and hashes. Qdrant holds document
embeddings for technical-document retrieval.

Implementation: [`database/schemas/001_initial.sql`](../database/schemas/001_initial.sql).

## 2. Relationship overview

```text
ORGANIZATION
    +---- USERS ---- ORGANIZATION_MEMBERS
    +---- FACTORIES
            +---- PRODUCTION_LINES ---- MACHINES
            +---- PRODUCTION_BATCHES
                    +---- PRODUCTION_EVENTS
                    +---- FABRIC_IMAGES ---- INSPECTION_RESULTS ---- DETECTED_DEFECTS

MACHINES
    +---- MACHINE_SENSORS ---- SENSOR_READINGS
    +---- MACHINE_PREDICTIONS ---- MAINTENANCE_RECOMMENDATIONS
    +---- MAINTENANCE_RECORDS

FACTORIES / BATCHES / MACHINES
    +---- INVESTIGATIONS
            +---- INVESTIGATION_EVIDENCE
            +---- ROOT_CAUSE_HYPOTHESES
            +---- AGENT_RUNS ---- AGENT_ACTIONS

MODEL_VERSIONS  <-- referenced by INSPECTION_RESULTS and MACHINE_PREDICTIONS
```

## 3. Engineering rules

- UUID primary keys everywhere.
- `organization_id` on every tenant-owned table, backed by row-level security.
- Index `(machine_id, timestamp)` for telemetry; `(organization_id, <time>)` for dashboards.
- Partition or hypertable the sensor table before production volumes; do not guess the chunk
  interval — measure ingest rate first.
- JSONB only for flexible metadata. Anything filtered or joined becomes a column.
- Image files stay in object storage. Never store binaries in a row.
- Preserve model and dataset version references so any prediction can be traced back to the
  artifact and training data that produced it.
- Wrap related state changes in a transaction.
- Never trust a client-supplied `organization_id`: resolve membership from the session, set
  `app.current_org`, let RLS enforce the rest.

## 4. Tenant isolation

```sql
SET LOCAL app.current_org = '<resolved organization uuid>';
SELECT * FROM machines;   -- only that organization's rows are visible
```

The policy is applied per request inside the transaction. Tables that lack their own
`organization_id` (e.g. `detected_defects`) inherit isolation through an `EXISTS` check against
their parent row.

## 5. Where the research data model earns its keep

`sensor_readings` + `production_events` + `inspection_results` + `maintenance_records` share a
machine identifier and a timestamp. That intersection is what makes the root cause engine
possible: for any inspection, the engine can pull the telemetry window that preceded it, the
production events during it, and the maintenance record before it. Without the shared keys, the
same analysis degrades into manual spreadsheet work.

## 6. Migration policy

Migrations are additive and versioned (`database/migrations/NNN_description.sql`). Destructive
changes require a two-step deploy: add the new shape, backfill, then remove the old one.
