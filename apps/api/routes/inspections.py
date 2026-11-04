"""Fabric inspection endpoints (Module C: FR-013 to FR-021).

The image arrives as a raw body with an image content type rather than multipart form data. Reasons:
multipart needs an extra parser dependency and a temp-file dance for one file, and raw bytes make the
CLI example a single curl. The trade is that only one image per request, which matches how a camera
gateway sends frames.

Storage and inference happen in this request because the baseline detector takes milliseconds. When a
trained model replaces it, this handler enqueues and returns 202 — the response shape already carries
`inference_duration_ms` so that change is visible to clients rather than silent.
"""

from __future__ import annotations

import json
import time
from uuid import UUID

from core.config import get_settings
from core.errors import NotFound, PayloadTooLarge, UnprocessableEntity
from core.security import Principal
from deps import get_tenant_db, require_role
from fastapi import APIRouter, Depends, Query, Request
from schemas.inspection import DefectOut, InspectionResponse
from services.inspection import record_inspection
from services.vision_baseline import detect
from sqlalchemy import text
from sqlalchemy.orm import Session

router = APIRouter(prefix="/inspections", tags=["inspections"])

ALLOWED_PREFIX = "image/"


@router.post(
    "",
    response_model=InspectionResponse,
    status_code=201,
    summary="Inspect one fabric image",
)
async def create_inspection(
    request: Request,
    machine_id: UUID | None = Query(default=None),
    batch_id: UUID | None = Query(default=None),
    camera_id: str | None = Query(default=None, max_length=64),
    principal: Principal = Depends(require_role("quality_inspector")),
    db: Session = Depends(get_tenant_db),
) -> InspectionResponse:
    """Run the vision baseline over an uploaded image and store the result.

    `machine_id` and `batch_id` are optional but valuable: without them the defect cannot be
    correlated with telemetry later, which is the entire premise of the root cause engine (FR-020).
    """
    settings = get_settings()

    content_type = request.headers.get("content-type", "")
    if not content_type.startswith(ALLOWED_PREFIX):
        raise UnprocessableEntity(
            "Send the image as a raw body with an image content type (e.g. image/jpeg).",
            requirement="FR-013",
        )

    image_bytes = await request.body()
    if not image_bytes:
        raise UnprocessableEntity("The request body is empty.", requirement="FR-013")

    # Checked before decoding: a decoded 15 MB image can occupy hundreds of megabytes of RAM.
    if len(image_bytes) > settings.vision_max_upload_bytes:
        raise PayloadTooLarge(
            f"Image exceeds the {settings.vision_max_upload_bytes} byte limit.",
            requirement="FR-013",
        )

    started = time.perf_counter()
    try:
        result = detect(image_bytes)
    except ValueError as exc:
        raise UnprocessableEntity(str(exc), requirement="FR-013") from exc
    duration_ms = int((time.perf_counter() - started) * 1000)

    # duration is measured outside the detector so it includes decode, which is what a client waits
    # for. The dataclass is frozen, so it is rebuilt rather than mutated.
    result = type(result)(
        width=result.width,
        height=result.height,
        status=result.status,
        defects=result.defects,
        duration_ms=duration_ms,
        detector=result.detector,
    )

    stored = record_inspection(
        db,
        principal,
        image_bytes,
        result,
        directory=settings.vision_upload_dir,
        machine_id=machine_id,
        batch_id=batch_id,
        camera_id=camera_id,
    )

    return InspectionResponse(
        id=stored.inspection_id,
        fabric_image_id=stored.fabric_image_id,
        overall_status=result.status,
        width=result.width,
        height=result.height,
        inference_duration_ms=duration_ms,
        detector=result.detector,
        defects=[
            DefectOut(
                defect_class=d.defect_class,
                confidence=d.confidence,
                x=d.x,
                y=d.y,
                w=d.w,
                h=d.h,
                severity=d.severity,
                area_fraction=d.area_fraction,
            )
            for d in result.defects
        ],
    )


@router.get(
    "/{inspection_id}",
    response_model=InspectionResponse,
    summary="Read one stored inspection",
)
def read_inspection(
    inspection_id: UUID,
    principal: Principal = Depends(require_role("quality_inspector")),
    db: Session = Depends(get_tenant_db),
) -> InspectionResponse:
    row = db.execute(
        text(
            """
            SELECT r.id, r.fabric_image_id, r.overall_status, r.inference_duration_ms,
                   i.image_width, i.image_height
            FROM inspection_results r
            JOIN fabric_images i ON i.id = r.fabric_image_id
            WHERE r.id = :id
            """
        ),
        {"id": inspection_id},
    ).first()

    if row is None:
        # RLS already hides other tenants' rows, so "not found" is the honest answer: whether an id
        # exists elsewhere is not this caller's business.
        raise NotFound("Inspection not found.")

    defects = db.execute(
        text(
            """
            SELECT defect_class, confidence_score, bounding_box, severity
            FROM detected_defects
            WHERE inspection_result_id = :id
            ORDER BY confidence_score DESC
            """
        ),
        {"id": inspection_id},
    ).all()

    return InspectionResponse(
        id=row[0],
        fabric_image_id=row[1],
        overall_status=row[2],
        width=row[4] or 0,
        height=row[5] or 0,
        inference_duration_ms=row[3] or 0,
        detector="stored",
        defects=[
            DefectOut(
                defect_class=d[0],
                confidence=float(d[1]),
                x=json.loads(d[2])["x"] if isinstance(d[2], str) else d[2]["x"],
                y=json.loads(d[2])["y"] if isinstance(d[2], str) else d[2]["y"],
                w=json.loads(d[2])["w"] if isinstance(d[2], str) else d[2]["w"],
                h=json.loads(d[2])["h"] if isinstance(d[2], str) else d[2]["h"],
                severity=d[3],
                area_fraction=0.0,
            )
            for d in defects
        ],
    )
