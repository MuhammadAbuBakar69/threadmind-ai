# Infrastructure

| Directory | Contents |
|---|---|
| `docker/` | Dockerfiles, broker configuration |
| `cloud/` | Managed-service provisioning notes per environment |
| `monitoring/` | Prometheus scrape config, Grafana dashboards, alert rules |
| `ci-cd/` | Deployment pipeline definitions |

The authoritative CI workflow lives at [`.github/workflows/ci.yml`](../.github/workflows/ci.yml).

## Rules

- No secrets in images, compose files, or repository history. `.env.example` documents names only.
- Model artifacts are pulled by URI at runtime, not baked into the image.
- Migrations run as a release step, never concurrently with replicas.
- Every service exposes a health endpoint; readiness fails when a critical dependency is down.
