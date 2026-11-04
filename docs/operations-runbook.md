# Operations Runbook

Written for the person on call at 02:00 who did not build this. Every command assumes nothing about
memory. Nothing here has been rehearsed against a live cloud deployment yet; where that matters it
says so.

---

## 1. Service map

| Service | Port | Health | Depends on |
|---|---|---|---|
| `api` (FastAPI) | 8000 | `/health`, `/health/ready` | PostgreSQL |
| `web` (Next.js) | 3000 | `/` | api |
| PostgreSQL + Timescale | 5432 | `pg_isready` | — |
| Redis | 6379 | `redis-cli ping` | — |
| MinIO | 9000 | `/minio/health/live` | — |
| Qdrant | 6333 | `/healthz` | — |
| Mosquitto | 1883 | `mosquitto_sub -t '$SYS/#'` | — |

---

## 2. Deploy

```bash
# 1. Build and push (CI does this on main; manual fallback)
docker build -f infrastructure/docker/Dockerfile.api -t ghcr.io/muhammadabubakar69/threadmind-ai-api:$TAG .
docker push ghcr.io/muhammadabubakar69/threadmind-ai-api:$TAG

# 2. Migrations run as a controlled step, never at container boot.
#    A boot-time migration makes a failed migration into a restart loop.
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f database/schemas/001_initial.sql   # first install only
for f in database/migrations/[0-9]*.sql; do
  echo "applying $f"
  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$f"
done

# 3. Roll out
docker service update --image ghcr.io/.../threadmind-ai-api:$TAG threadmind_api
```

**Pre-deploy checks**

- [ ] `pytest -q` green (unit + API)
- [ ] Database jobs green in CI (**not** just the unit job)
- [ ] `JWT_SECRET` set to a real value; production refuses to start with the placeholder (SEC-003)
- [ ] Migrations reviewed for lock duration on large tables
- [ ] Rollback migration exists for anything new

---

## 3. Database role (do not skip)

The application must connect as a **non-superuser** role. A superuser bypasses row-level security
regardless of `FORCE`, and every isolation test in the suite becomes meaningless.

```sql
CREATE ROLE threadmind_app LOGIN PASSWORD '<from-vault>';
GRANT USAGE ON SCHEMA public TO threadmind_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO threadmind_app;
-- No CREATE, no DDL, no SUPERUSER, no BYPASSRLS.
```

Verify:

```sql
SELECT rolname, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = 'threadmind_app';
-- rolsuper = f, rolbypassrls = f
```

---

## 4. Backup and restore

```bash
# Nightly logical backup (retain 14 days; verify size trend, not just exit code)
pg_dump "$DATABASE_URL" --format=custom --file=/backups/threadmind-$(date +%F).dump

# Object storage: images and model artifacts
mc mirror --overwrite minio/threadmind-artifacts s3://threadmind-backup/artifacts/$(date +%F)/
```

**Restore rehearsal (required before any pilot, not yet performed):**

```bash
createdb threadmind_restore
pg_restore --clean --if-exists --dbname=threadmind_restore /backups/threadmind-2026-11-04.dump
psql threadmind_restore -c "SELECT count(*) FROM machines;"   # expect a real number
```

A backup that has never been restored is a hypothesis. Record the date of the last rehearsal and the
time it took.

---

## 5. Incident procedures

### 5.1 Ingest rejection rate above 5%

Read the reason distribution returned by `/api/v1/telemetry`; it distinguishes the causes:

| Reason | Meaning | Action |
|---|---|---|
| `value outside plausible range` | Unit error, wrong sensor mapping, stuck sensor | Check gateway config and the specific sensor |
| `timestamp ... in the future` | Device clock drift | Fix NTP on the gateway; readings are being **rejected**, not stored wrong |
| `duplicate event_id in batch` | Gateway retry storm | Confirm the gateway backs off |
| `organization_id` mismatch (403) | Misconfigured gateway or forgery attempt | **Treat as security event**; check `audit_logs` |

### 5.2 Readiness degraded

`/health/ready` returns `{"status":"degraded","detail":"database_unreachable:...}`. The detail names
the failure category only. Check the database first, then pool exhaustion (`pg_stat_activity`).

### 5.3 Suspected cross-tenant access

1. Do not restart anything; you will lose the evidence.
2. Query audit and access logs for `status=403` with code `insufficient_role` on `/telemetry`.
3. Confirm the deployed role: `SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user;`
   A superuser connection is the most likely cause, and it is a deployment error, not an attack.
4. If RLS is the issue, re-apply `002_rls_hardening.sql`; it is idempotent.

### 5.4 Rollback a bad migration

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f database/migrations/900_rollback_002.sql
```

`900_rollback_002.sql` removes policies and drops the indexes added by `002`. It does **not** drop
tables, so it is safe to run while the previous version is still serving. Re-applying `002` afterwards
restores isolation: leaving the rollback in place means the owner bypasses RLS again.

### 5.5 Agent producing unsupported claims

Disable the agent's workflow, keep the `agent_runs` rows (they are the audit trail), and re-run the
case once the evidence validator is fixed. Never delete a run to make a report look clean.

---

## 6. Routine checks

**Daily:** readiness green; ingest rejection rate < 1%; no 5xx spike; backup file present and
non-trivial in size.

**Weekly:** review rejection interviews by reason; check queue depth trend (once a queue exists);
confirm the last backup restore date is within 30 days.

**Monthly:** rotate `JWT_SECRET` once an IdP is in place (rotating the current shared secret logs
everyone out); review `audit_logs` for denied access patterns; re-run the load test.

---

## 7. Local development

```bash
cp .env.example .env
docker compose up -d postgres redis minio qdrant mosquitto
psql "$DATABASE_URL" -f database/schemas/001_initial.sql
for f in database/migrations/[0-9]*.sql; do psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$f"; done
uvicorn main:app --reload --app-dir apps/api --port 8000
python scripts/dev_token.py --role factory_admin        # development token (SEC-002)
python ai-services/telemetry/simulator.py --scenario bearing_degradation --minutes 30 --out data/synthetic/dev
```

**The compose stack is a development topology and nothing else.** Anonymous MQTT, trivial MinIO
credentials, no TLS, no resource limits, single replica, and no backup. Do not expose it to a network
you do not control, and do not present it as a deployment.
