"""Error contract.

Two reasons this is explicit rather than left to FastAPI's defaults:

1. A client integrating with an industrial platform needs a stable machine-readable code. Prose
   messages change; codes are a contract.
2. Default handlers leak. An unhandled exception returns a 500 whose body can carry a traceback,
   a SQL fragment, or a connection string. Nothing internal leaves this API: the client receives a
   code, a safe message, and the request id needed to find the full detail in the logs.

`requirement` links a failure back to the SRS item it protects, which keeps error handling tied to
scope instead of becoming guesswork.
"""

from __future__ import annotations

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    """Base class for every deliberate failure the API can produce."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "bad_request"
    requirement: str | None = None

    def __init__(
        self,
        message: str = "Request could not be completed.",
        *,
        requirement: str | None = None,
    ) -> None:
        self.message = message
        # The requirement can be narrowed per raise site: UnprocessableEntity is used by several
        # modules (telemetry, inspections) and the SRS reference is more useful when it names the one
        # that actually failed.
        if requirement is not None:
            self.requirement = requirement
        super().__init__(message)


class Unauthenticated(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthenticated"
    requirement = "FR-001"


class Forbidden(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "insufficient_role"
    requirement = "FR-002"


class NotFound(AppError):
    """Also used for another tenant's record.

    Returning 404 instead of 403 is deliberate: a 403 confirms the record exists, which leaks the
    existence of other organizations' machines and batches.
    """

    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"
    requirement = "FR-004"


class Conflict(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


class UnprocessableEntity(AppError):
    status_code = 422
    code = "invalid_payload"


class PayloadTooLarge(AppError):
    """Upload exceeded the configured limit.

    413 rather than 400: the body was well formed, it was simply too big, and a client that retries
    the same bytes should be told that rather than guess the schema is wrong.
    """

    status_code = 413


class RateLimited(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limited"
    requirement = "FR-001"


class ServiceUnavailable(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "service_unavailable"


def error_body(code: str, message: str, request_id: str, requirement: str | None = None) -> dict:
    payload: dict = {"error": {"code": code, "message": message}, "request_id": request_id}
    if requirement:
        payload["error"]["requirement"] = requirement
    return payload


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    headers = {"X-Request-ID": _request_id(request)}
    if isinstance(exc, Unauthenticated):
        headers["WWW-Authenticate"] = "Bearer"
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(exc.code, exc.message, _request_id(request), exc.requirement),
        headers=headers,
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Report which fields failed, without echoing submitted values.

    Echoing the value is convenient until the field is a credential or a signed URL, so only the
    location and the reason are returned.
    """
    fields = [
        {"location": ".".join(str(part) for part in error["loc"]), "reason": error["msg"]}
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "invalid_payload",
                "message": "Request payload failed validation.",
                "fields": fields,
            },
            "request_id": _request_id(request),
        },
    )


async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(
            {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error"),
            str(exc.detail),
            _request_id(request),
        ),
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Last line of defence: log everything, disclose nothing.

    The client gets a correlation id; the traceback stays in the logs where it belongs.
    """
    request_id = _request_id(request)
    import logging

    logging.getLogger("threadmind.error").exception(
        "unhandled_exception request_id=%s path=%s", request_id, request.url.path
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_body(
            "internal_error",
            "An unexpected error occurred. Quote the request id when reporting it.",
            request_id,
        ),
    )
