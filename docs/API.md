# API Surface

Base path: `/api/v1`. All endpoints authenticate with a bearer token; every request resolves the
caller's organization membership server-side.

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
