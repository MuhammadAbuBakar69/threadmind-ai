"""Shared response shapes."""

from typing import Literal

from pydantic import BaseModel


class ErrorBody(BaseModel):
    code: str
    message: str
    requirement: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = "threadmind-api"
    version: str


class ReadinessResponse(BaseModel):
    status: Literal["ready", "degraded"]
    database: bool
    detail: str | None = None
    environment: str | None = None
