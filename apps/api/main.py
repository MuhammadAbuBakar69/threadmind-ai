"""ThreadMind AI — API entry point.

Layer 2 of the architecture: authentication integration, business logic, validation, data access,
and service communication. Long-running AI work must be enqueued, never awaited inline.
"""

from core.config import get_settings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from middleware.tenant import TenantContextMiddleware
from routes import health

settings = get_settings()

app = FastAPI(
    title="ThreadMind AI",
    version=health.VERSION,
    description=(
        "Industrial intelligence API for textile manufacturing. "
        "Specialized ML models produce numerical predictions; agents orchestrate, "
        "explain, and cite evidence."
    ),
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.add_middleware(TenantContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"] if not settings.is_production else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(health.router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {
        "service": "threadmind-api",
        "docs": "/docs",
        "scope": "decision support only — no machine control (FR-048)",
    }
