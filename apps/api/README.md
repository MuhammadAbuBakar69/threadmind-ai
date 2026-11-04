# apps/api — FastAPI application layer

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

`http://localhost:8000/docs` for the interactive reference.

## Layout

| Path | Contents |
|---|---|
| `main.py` | App assembly, middleware, routers |
| `core/config.py` | Environment-driven settings |
| `core/security.py` | Principal resolution and organization scoping |
| `db.py` | Session factory |
| `routes/` | HTTP endpoints, one module per SRS module |
| `schemas/` | Pydantic request/response models |
| `middleware/` | Request context |
| `services/` | Business logic, kept out of route handlers |

## Non-negotiables

1. A client-supplied `organization_id` is a claim, not an authorization. Resolve membership, then
   `SET LOCAL app.current_org` so RLS enforces isolation.
2. Numerical predictions come from a model version recorded in `model_versions`, never from an LLM.
3. Long AI work is enqueued. The request returns a job reference; the client polls or subscribes.
