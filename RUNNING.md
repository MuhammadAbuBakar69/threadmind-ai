# Running ThreadMind AI

Three commands to a working system. This is the honest quickstart: what works today, and what does
not yet.

```bash
cp .env.example .env          # add your Clerk keys (see below)
docker compose up -d postgres redis minio mosquitto api
docker compose exec api python -m scripts.seed_demo 2>/dev/null || python scripts/seed_demo.py
```

Then open <http://localhost:8000/docs>. The API is live and every endpoint below is real.

## 1. Sign in

The dashboard uses Clerk. Put your keys in `.env`:

```
CLERK_ISSUER=https://<your-instance>.clerk.accounts.dev
CLERK_SECRET_KEY=sk_...
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_...
```

Create a user in the Clerk dashboard, then link it to the seeded tenant so it has somewhere to act:

```bash
python scripts/link_clerk_identity.py \
  --email you@example.com \
  --clerk-user-id user_... \
  --clerk-org-id org_... \
  --org-name "Demo Textile Mills" \
  --role factory_admin
```

Both ids are visible in the Clerk dashboard. Until this runs, sign-in succeeds and every call returns
403 — deliberately: authentication is not authorization.

## 2. Inspect a fabric image

```bash
TOKEN=$(...Clerk session token...)
curl -X POST "http://localhost:8000/api/v1/inspections?machine_id=11111111-1111-4111-8111-111111111115" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: image/jpeg" \
  --data-binary @fabric.jpg
```

```json
{
  "id": "…",
  "overall_status": "fail",
  "inference_duration_ms": 42,
  "detector": "texture-anomaly-baseline/1",
  "detector_kind": "baseline_untrained",
  "defects": [
    {"defect_class": "dark_region", "confidence": 0.97, "x": 146, "y": 96, "w": 28, "h": 28,
     "severity": "major"}
  ]
}
```

`detector_kind: baseline_untrained` is in the payload because it matters: this detector finds regions
that differ from the rest of the same image. It does not know what a hole is, its confidence is not a
calibrated probability, and it has never seen a labelled defect. It exists so the upload → inspect →
store → overlay path is real today. A trained model replaces it behind the same endpoint.

## 3. Send machine telemetry

```bash
python -m industrial.telemetry.simulator --machine 11111111-1111-4111-8111-111111111115 --minutes 5
```

Deterministic: the same seed produces the same readings, which is what makes experiment results
reproducible (#18).

## What works, and what does not

| Capability | State |
|---|---|
| Multi-tenant isolation (forced RLS, tested) | works |
| Clerk login, roles resolved from the database | works |
| Fabric image upload, defect boxes, stored results | works (baseline detector, untrained) |
| Telemetry ingest, validation, dead-lettering | works |
| OEE calculation | works |
| Trained defect model (YOLO/U-Net) | **not built** — needs labelled data |
| Predictive maintenance models | **not built** — needs sensor history |
| The five AI agents | **not built** — no model to ground them |
| Live dashboard screens | **minimal** — auth + API client only |

The bottom four rows are not code problems. They need data, and data needs a factory or a dataset
you have the right to use. Everything above them is infrastructure that should already work when
that data arrives.

## Troubleshooting

| Symptom | Cause |
|---|---|
| `AUTH_PROVIDER must be 'clerk' in production` | Correct. The dev provider signs tokens with a shared secret; production refuses it. |
| Every call returns 403 | The Clerk account is not linked to a tenant yet. Run `link_clerk_identity.py`. |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY is not set` at build | The dashboard refuses to build without it, rather than shipping a broken login. |
| 413 on upload | `VISION_MAX_UPLOAD_BYTES` (default 15 MB). |
