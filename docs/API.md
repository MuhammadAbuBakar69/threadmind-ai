# API Surface

Base path: `/api/v1`. All endpoints authenticate with a bearer token; every request resolves the
caller's organization membership server-side.

**Implemented today:** `/health`, `/health/ready`, `POST /api/v1/telemetry`. Everything else below is
the target surface and is not routed yet — see `docs/issue-traceability.md`.

## Conventions

Every response carries `X-Request-ID`. Supply your own to correlate with your logs; an id that is not
`[A-Za-z0-9._-]{8,64}` is replaced.

Errors always use one envelope:

```json
{
  "error": {
    "code": "insufficient_role",
    "message": "This action requires the factory_admin role.",
    "requirement": "FR-002"
  },
  "request_id": "6b1f0e2c9a4d4f0e8c3b5a7d9e1f2a3b"
}
```

Validation failures add `error.fields[]` with locations and reasons; submitted values are never
echoed. Status codes in use: `401` unauthenticated, `403` insufficient role, `404` not found **or
another tenant's record** (a 403 would confirm it exists), `409` conflict, `422` invalid payload,
`429` rate limited, `500` internal (message only, no traceback).

Rate limit: 120 requests / 60 s per caller, `Retry-After` on 429. Health endpoints are exempt.

## Telemetry

| Method | Path | Requirement |
|---|---|---|
| POST | `/telemetry` | FR-022, FR-023 |

Accepts `{"readings": [...]}` (1-1000). Requires `production_supervisor` or above. `202` means
validated and stored; downstream scoring is asynchronous.

```json
{"accepted": 998, "duplicates": 1, "rejected": [{"event_id": "…", "reason": "value: 950.0degC outside plausible range -40.0-400.0degC"}], "rejection_rate": 0.001}
```

A reading whose `organization_id` differs from the caller's is refused with `403` — tenant scope comes
from the token, never the payload. Duplicates are counted, not stored twice: the natural key is
`(machine_id, sensor_id, timestamp)`.

## Health

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness, version, build info |
| GET | `/health/ready` | Readiness: database and queue reachability |

## Organization and access

| Method | Path | Notes |
|---|---|---|
| GET | `/me` | Current user and memberships |
| GET | `/organizations/{id}/members` | Requires `factory_admin` or above |
| POST | `/organizations/{id}/invitations` | FR-005 |

## Factories and machines

| Method | Path | Requirement |
|---|---|---|
| POST | `/factories` | FR-007 |
| GET | `/factories` | FR-008 |
| POST | `/factories/{id}/lines` | FR-008 |
| POST | `/machines` | FR-009 |
| GET | `/machines/{id}` | FR-011 |
| GET | `/machines/{id}/history` | FR-012 |

## Quality inspection

| Method | Path | Requirement |
|---|---|---|
| POST | `/inspections` | FR-013, FR-018 — accepts an image reference, enqueues inference |
| GET | `/inspections/{id}` | FR-016, FR-017 |
| POST | `/inspections/{id}/verify` | FR-019 — inspector confirms or corrects |
| GET | `/factories/{id}/quality-summary` | FR-021 |

## Telemetry and maintenance

| Method | Path | Requirement |
|---|---|---|
| POST | `/telemetry` | FR-022, FR-023 — HTTP ingestion; MQTT is the primary path |
| GET | `/machines/{id}/condition` | FR-026, FR-029 |
| POST | `/maintenance-records` | FR-028 |
| POST | `/recommendations/{id}/approve` | FR-047 — human approval gate |

## Investigations

| Method | Path | Requirement |
|---|---|---|
| POST | `/investigations` | FR-030 |
| GET | `/investigations/{id}` | FR-033, FR-034, FR-035 |
| POST | `/investigations/{id}/review` | FR-036 |

## Analytics and exports

| Method | Path | Requirement |
|---|---|---|
| GET | `/analytics/overview` | FR-049 |
| GET | `/analytics/trends` | FR-050, FR-054 |
| GET | `/analytics/export.csv` | FR-053 |
| POST | `/reports/pdf` | FR-052 |

## Error contract

Errors return a stable machine-readable shape:

```json
{ "error": { "code": "insufficient_role", "message": "factory_admin required", "requirement": "FR-002" } }
```

`404` is returned instead of `403` for a resource that belongs to another organization, so the
API does not confirm the existence of other tenants' records.
