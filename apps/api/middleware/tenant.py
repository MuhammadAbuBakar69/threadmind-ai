"""Request context.

Placeholder for the gateway-level wiring: extract the bearer token, resolve the user, and attach
the resolved principal to `request.state` so route handlers never parse organization claims
themselves.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class TenantContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        request.state.principal = None
        response = await call_next(request)
        response.headers["X-ThreadMind-Tenant-Scoped"] = "true"
        return response
