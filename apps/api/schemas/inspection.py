"""Inspection request and response shapes (API.md contract for Module C)."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class DefectOut(BaseModel):
    defect_class: str
    confidence: float = Field(ge=0, le=1)
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    w: int = Field(gt=0)
    h: int = Field(gt=0)
    severity: Literal["minor", "major", "critical"]
    area_fraction: float = Field(ge=0, le=1)


class InspectionResponse(BaseModel):
    id: UUID
    fabric_image_id: UUID
    overall_status: Literal["pass", "fail", "uncertain"]
    width: int
    height: int
    inference_duration_ms: int
    detector: str
    defects: list[DefectOut] = Field(default_factory=list)
    # Stated in the payload, not buried in docs: this baseline is not a trained defect classifier.
    detector_kind: Literal["baseline_untrained"] = "baseline_untrained"


class InspectionSummary(BaseModel):
    id: UUID
    overall_status: Literal["pass", "fail", "uncertain"]
    created_at: str
    defect_count: int
