# Getting ThreadMind online

Three routes, in order of how much of your evening they cost. All three end with a real HTTPS URL
running the same image that passed CI.

**Neither route removes the one manual step that remains: linking your Clerk account to a factory.**
Until that is done, sign-in succeeds and every data call is refused. That is deliberate (see
`docs/authentication.md`) — an unknown account must not be able to create a tenant that then holds
real data.

---

## Route A — Render, from this repository (about 15 minutes)

`render.yaml` is a blueprint: the API container, a managed PostgreSQL 16, and the Next.js dashboard.

1. Push this repo to GitHub (already done).
2. Render → **New → Blueprint** → select the repository.
3. It will ask for four values, because they are marked `sync: false` and therefore never live in git:
   - `CLERK_ISSUER` — `https://fine-crane-1297.clerk.accounts.dev`
   - `CLERK_SECRET_KEY` — from the Clerk dashboard
   - `CLERK_AUTHORIZED_PARTIES` — the dashboard URL Render assigns, once you know it
   - `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `NEXT_PUBLIC_API_BASE_URL`
     (`https://<api-service>.onrender.com/api/v1`)
4. Deploy. The API applies the schema and forward migrations on boot (`RUN_MIGRATIONS=1`).

**Cost, honestly:** the `starter` plans are not free. Free instances sleep after inactivity and this
API holds a migration lock and (later) an MQTT session, so sleeping is not cosmetic here.

## Route B — one VPS with Docker (about 30 minutes, cheapest long-term)

Any 2 vCPU / 4 GB Ubuntu box with a domain pointing at it.

```bash
git clone https://github.com/MuhammadAbuBakar69/threadmind-ai
cd threadmind-ai
export DOMAIN=threadmind.yourdomain.com
export POSTGRES_PASSWORD="$(openssl rand -base64 24)"
export CLERK_ISSUER=https://fine-crane-1297.clerk.accounts.dev
export CLERK_SECRET_KEY=sk_live_...
docker compose -f docker-compose.prod.yml up -d
```

Caddy fetches the certificate. `docker compose -f docker-compose.prod.yml logs -f api` shows the
migration output on first boot.

## Route C — GitHub Container Registry, anywhere that runs a container

CI already builds and pushes `ghcr.io/muhammadabubakar69/threadmind-ai-api:main` on every merge to
main. **It is currently a private package**, so the host must be given a registry credential until it
is made public in the repository's package settings.

```bash
docker run -p 8000:8000 \
  -e DATABASE_URL=postgresql+psycopg://user:pass@host:5432/threadmind \
  -e APP_ENV=production -e AUTH_PROVIDER=clerk \
  -e CLERK_ISSUER=https://fine-crane-1297.clerk.accounts.dev \
  -e CLERK_SECRET_KEY=sk_live_... \
  -e RUN_MIGRATIONS=1 \
  ghcr.io/muhammadabubakar69/threadmind-ai-api:main
```

---

## Verify the deployment

```bash
curl https://<host>/health          # {"status":"ok",...}
curl https://<host>/health/ready    # database reachable, migrations applied
```

`/health/ready` returning 503 is the correct answer when the database is not reachable, and is what
the platform health check uses.

Then, once, with the production `DATABASE_URL`:

```bash
DATABASE_URL=... python scripts/seed_demo.py --email you@example.com
```

That creates the demo factory and prints the Clerk user id to set in your Clerk account, or pass
`--clerk-user-id user_...` to link an existing account.

## What is still missing before a factory uses this

- **No trained model.** The inspector is the untrained baseline; the API labels its own output
  `baseline_untrained` so no one mistakes it for a validated detector.
- **No alerts, no dashboard screens, no agents.** Issues #16–#20.
- **Uploads land on local disk** (`VISION_UPLOAD_DIR`). On a host with ephemeral storage they vanish
  on redeploy; object storage is the follow-up.
- **One machine, one database, no replicas.** Backups are documented in
  `docs/operations-runbook.md` and are not automatic.

Listing these here is not modesty, it is the difference between a demo someone trusts and a demo
someone deploys into a production line.
