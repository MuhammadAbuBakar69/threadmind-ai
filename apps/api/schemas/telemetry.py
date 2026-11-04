"""Telemetry API response models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RejectionDetail(BaseModel):
    event_id: str
    reason: str


class IngestResponse(BaseModel):
    """Ingest outcome.

    Rejections are returned, not swallowed: a gateway operator needs to know that 4% of its traffic
    is malformed, and a silently-dropped reading is indistinguishable from a sensor that stopped
    reporting.
    """

    accepted: int = Field(ge=0)
    duplicates: int = Field(ge=0)
    rejected: list[RejectionDetail] = Field(default_factory=list)
    rejection_rate: float = Field(ge=0.0, le=1.0)
