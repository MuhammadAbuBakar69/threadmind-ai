# Deployment

## 1. Local

```bash
cp .env.example .env
docker compose up --build
```

Services: PostgreSQL 16, Redis 7, MinIO (S3-compatible), Qdrant, Mosquitto, FastAPI on `:8000`,
Next.js on `:3000`.

Apply the schema once the database is healthy:

```bash
psql "$DATABASE_URL" -f database/schemas/001_initial.sql
```

## 2. Target cloud topology

| Component | Hosting |
|---|---|
| Dashboard | Vercel or container hosting |
| API | Cloud container service |
| PostgreSQL | Managed instance |
| Object storage | S3-compatible managed bucket |
| Redis | Managed cache |
| MQTT | Managed or hardened cloud broker |
| Inference | Dedicated containers or managed endpoints |
| Observability | Prometheus + Grafana |

No single-vendor dependency. Managed equivalents are chosen per environment.

## 3. Environments

`development` → `staging` → `production`. Staging must run the production schema and the same
container images. Secrets are injected by the platform, never committed; `.env.example` documents
the names only.

## 4. Container images

`infrastructure/docker/Dockerfile.api` builds the API image. CI publishes to the registry on tags.
Model artifacts are pulled at runtime by URI (`MODEL_ARTIFACT_URI`), not baked into the image, so a
model can be rolled back without rebuilding the service.

## 5. Operational requirements

- Health checks on every service; readiness must fail when the database is unreachable.
- Migrations run as a release step, never concurrently with replicas.
- Backups: daily full, point-in-time recovery on the primary database.
- Alerting on error rate, P95 latency, queue depth, and inference failure rate.
- Model drift check on a schedule against a frozen reference window.

## 6. Availability target

99.5% for the pilot. This is a proposed target, to be validated against infrastructure cost and
factory connectivity reality, not an established service guarantee.
