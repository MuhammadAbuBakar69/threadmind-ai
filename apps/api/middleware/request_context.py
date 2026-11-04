"""Request correlation and access logging.

Every response carries `X-Request-ID`. A factory manager reporting "the dashboard failed at 09:14"
should be able to hand over one identifier that finds the exact request, tenant and duration in the
logs, instead of a timestamp and a guess.
"""

from __future__ import annotations

import logging
import re
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"
_VALID_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
_access_logger = logging.getLogger("threadmind.access")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        incoming = request.headers.get(REQUEST_ID_HEADER, "")
        # Accept a caller-supplied id only if it is shaped safely; it ends up in log output.
        request_id = incoming if _VALID_ID.match(incoming) else uuid.uuid4().hex
        request.state.request_id = request_id
        request.state.principal = None

        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = (time.perf_counter() - started) * 1000
            _access_logger.exception(
                "request_failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round(elapsed_ms, 2),
                },
            )
            raise

        elapsed_ms = (time.perf_counter() - started) * 1000
        response.headers[REQUEST_ID_HEADER] = request_id
        response.headers["X-ThreadMind-Tenant-Scoped"] = "true"

        _access_logger.info(
            "request_completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round(elapsed_ms, 2),
                "org": getattr(request.state.principal, "organization_id", None),
            },
        )
        return response
