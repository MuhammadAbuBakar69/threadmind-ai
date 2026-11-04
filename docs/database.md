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

## Row-level security: implementation notes

Four things have to be true for tenant isolation to be real. Three of them were false before the
audit, and each has a test now.

1. **`ENABLE` is not enough — `FORCE` is required.** A table owner bypasses its own policies. The
   application role must also be a non-superuser and must not hold `BYPASSRLS`. `002_rls_hardening.sql`
   forces RLS on all tenant tables; `tests/integration/test_tenant_isolation.py` connects as
   `threadmind_app` for exactly this reason.
2. **Child tables inherit through their parent.** `investigation_evidence`, `root_cause_hypotheses`
   and `agent_actions` carry no `organization_id`; their policies use `EXISTS` against the parent
   record, so a row whose parent belongs elsewhere is invisible no matter how it is queried.
3. **The scope must be parameterizable.** `SET LOCAL app.current_org = :org` cannot work: PostgreSQL's
   `SET` does not accept bind parameters. Use
   `SELECT set_config('app.current_org', :org, true)` — the third argument makes it transaction-local,
   so a pooled connection never carries one tenant's scope into the next request.
4. **Default deny, and deny must not raise.** With no scope set, `current_setting(..., true)` returns
   NULL and every policy evaluates false, so a query that forgets its `WHERE` clause returns zero
   rows. There is a test for this (`test_unscoped_connection_sees_nothing`).

   That test found a second-order bug worth recording: a custom GUC reverts to the **empty string**,
   not NULL, when a transaction-local setting ends. On a pooled connection that had previously served
   a scoped request, the policy then evaluated `''::uuid` and raised
   `invalid input syntax for type uuid: ""` instead of denying. Every policy therefore uses
   `NULLIF(current_setting('app.current_org', true), '')::uuid`. Deny-by-default has to return no
   rows, not an error.

### FORCE survives DISABLE

`ALTER TABLE ... DISABLE ROW LEVEL SECURITY` does not clear the FORCE flag. A rollback that only
disables leaves `relforcerowsecurity = true`, so the next `ENABLE` silently re-forces RLS on a table
nobody intended to force. Rollbacks must issue `NO FORCE` first; `900_rollback_002.sql` does, and the
CI rollback check asserts that zero tables remain forced afterwards.

### Telemetry idempotency

MQTT QoS 1 is at-least-once. `uq_readings_natural_key` on `(machine_id, sensor_id, "timestamp")` lets
the ingest path `ON CONFLICT DO NOTHING` and report duplicates separately, so a redelivery burst is
visible rather than inflating every window statistic derived from it.

### Global tables

`model_versions` is a registry readable by every tenant, because a prediction must be able to cite the
model version that produced it. `artifact_uri` must never appear in an API response.

### Known gaps

`created_at`/`updated_at` are missing on several tables, and `audit_logs` exists with no writer.
Both are tracked in #16 / #14 — see `docs/issue-traceability.md`.
