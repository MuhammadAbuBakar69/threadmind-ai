"""ThreadMind AI — API entry point.

Layer 2 of the architecture: authentication, business logic, validation, data access, and service
communication. Long-running AI work is enqueued, never awaited inline.

Middleware order is deliberate and runs outermost first:

    RequestContext  → assigns the correlation id before anything can fail
    RateLimit       → cheap rejection before parsing work
    CORS            → browser policy

Exception handlers guarantee that no traceback, query fragment, or connection string leaves the
process, regardless of which layer raised.
"""

from core.config import get_settings
from core.errors import (
    AppError,
    app_error_handler,
    http_error_handler,
    unhandled_error_handler,
    validation_error_handler,
)
from core.logging import configure_logging
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from middleware.rate_limit import RateLimitMiddleware
from middleware.request_context import RequestContextMiddleware
from routes import health, inspections, telemetry
from starlette.exceptions import HTTPException as StarletteHTTPException

configure_logging()
settings = get_settings()

app = FastAPI(
    title="ThreadMind AI",
    version=health.VERSION,
    description=(
        "Industrial intelligence API for textile manufacturing. Specialized ML models produce "
        "numerical predictions; agents orchestrate, explain, and cite evidence. Decision support "
        "only — no endpoint controls machinery."
    ),
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.add_middleware(RateLimitMiddleware, limit=120, window_seconds=60)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"] if not settings.is_production else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(StarletteHTTPException, http_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)

app.include_router(health.router)
app.include_router(health.router, prefix="/api/v1")
app.include_router(telemetry.router, prefix="/api/v1")
app.include_router(inspections.router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {
        "service": "threadmind-api",
        "docs": "/docs",
        "scope": "decision support only — no machine control (FR-048)",
    }
