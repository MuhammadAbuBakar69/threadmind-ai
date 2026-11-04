"""Fixed-window rate limiting.

Deliberately simple, and deliberately honest about it: the counter lives in process memory, so with
N replicas the effective limit is N times the configured one. That is adequate for a single-replica
research deployment and inadequate for production.

Blocker: distributed limiting needs Redis (`REDIS_URL` is already provisioned for it). Recorded as
finding SEC-005 and tracked in docs/security-review.md rather than quietly pretending this scales.
"""

from __future__ import annotations

import time
from collections import defaultdict

from core.errors import error_body
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# Paths that must stay reachable even under load, or an orchestrator cannot tell an overloaded
# service from a dead one.
EXEMPT_PATHS = frozenset({"/health", "/health/ready", "/metrics"})


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limit: int = 120, window_seconds: int = 60) -> None:
        super().__init__(app)
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits: dict[str, tuple[int, float]] = defaultdict(lambda: (0, 0.0))

    def _client_key(self, request: Request) -> str:
        # Prefer the token subject once authentication has run; fall back to the client address.
        principal = getattr(request.state, "principal", None)
        if principal is not None:
            return f"user:{principal.user_id}"
        return f"ip:{request.client.host if request.client else 'unknown'}"

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        now = time.monotonic()
        key = self._client_key(request)
        count, window_start = self._hits[key]

        if now - window_start >= self.window_seconds:
            count, window_start = 0, now

        count += 1
        self._hits[key] = (count, window_start)

        if count > self.limit:
            retry_after = max(1, int(self.window_seconds - (now - window_start)))
            request_id = getattr(request.state, "request_id", "unknown")
            return JSONResponse(
                status_code=429,
                content=error_body(
                    "rate_limited",
                    f"Rate limit of {self.limit} requests per {self.window_seconds}s exceeded.",
                    request_id,
                    "FR-001",
                ),
                headers={"Retry-After": str(retry_after), "X-Request-ID": request_id},
            )

        return await call_next(request)
