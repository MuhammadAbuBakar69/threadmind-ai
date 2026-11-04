"""Persisting an inspection.

Three rows, one transaction: the image record, the inspection result, and one row per detected
defect. If any insert fails the whole inspection is rolled back, because a result row without its
defects would be read by the dashboard as "clean".
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from core.security import Principal
from sqlalchemy import text

from services.vision_baseline import DetectionResult, content_hash

INSERT_IMAGE = """
INSERT INTO fabric_images
    (organization_id, batch_id, machine_id, storage_key, image_hash,
     image_width, image_height, captured_at, camera_id, metadata)
VALUES
    (:organization_id, :batch_id, :machine_id, :storage_key, :image_hash,
     :image_width, :image_height, :captured_at, :camera_id, CAST(:metadata AS jsonb))
RETURNING id
"""

INSERT_RESULT = """
INSERT INTO inspection_results
    (organization_id, fabric_image_id, overall_status, inference_duration_ms)
VALUES
    (:organization_id, :fabric_image_id, :overall_status, :inference_duration_ms)
RETURNING id
"""

INSERT_DEFECT = """
INSERT INTO detected_defects
    (inspection_result_id, defect_class, confidence_score, bounding_box, severity)
VALUES
    (:inspection_result_id, :defect_class, :confidence_score, CAST(:bounding_box AS jsonb), :severity)
"""


@dataclass(frozen=True)
class StoredInspection:
    inspection_id: UUID
    fabric_image_id: UUID
    storage_key: str


def store_image(image_bytes: bytes, organization_id: UUID, *, directory: str) -> str:
    """Write the image under its content hash and return the storage key.

    Local filesystem, deliberately, while there is no object store in the request path: the
    interface is "give me a key", so moving to S3 replaces this function and nothing else. The
    filename is the SHA-256 of the bytes, which makes a duplicate upload idempotent instead of
    doubling storage.
    """
    digest = content_hash(image_bytes)
    root = Path(directory)
    target = root / str(organization_id) / f"{digest}.bin"
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        # Write-then-rename: a half-written file under the hash of its full contents would be a
        # cache that lies.
        staging = target.with_suffix(".part")
        staging.write_bytes(image_bytes)
        os.replace(staging, target)
    return str(Path(str(organization_id)) / f"{digest}.bin")


def record_inspection(
    db,
    principal: Principal,
    image_bytes: bytes,
    result: DetectionResult,
    *,
    directory: str,
    machine_id: UUID | None = None,
    batch_id: UUID | None = None,
    camera_id: str | None = None,
) -> StoredInspection:
    storage_key = store_image(image_bytes, principal.organization_id, directory=directory)

    fabric_image_id = db.execute(
        text(INSERT_IMAGE),
        {
            "organization_id": principal.organization_id,
            "batch_id": batch_id,
            "machine_id": machine_id,
            "storage_key": storage_key,
            "image_hash": content_hash(image_bytes),
            "image_width": result.width,
            "image_height": result.height,
            "captured_at": datetime.now(UTC),
            "camera_id": camera_id,
            "metadata": json.dumps({"detector": result.detector}),
        },
    ).scalar_one()

    inspection_id = db.execute(
        text(INSERT_RESULT),
        {
            "organization_id": principal.organization_id,
            "fabric_image_id": fabric_image_id,
            "overall_status": result.status,
            "inference_duration_ms": result.duration_ms,
        },
    ).scalar_one()

    for defect in result.defects:
        db.execute(
            text(INSERT_DEFECT),
            {
                "inspection_result_id": inspection_id,
                "defect_class": defect.defect_class,
                "confidence_score": defect.confidence,
                "bounding_box": json.dumps(defect.as_box()),
                "severity": defect.severity,
            },
        )

    return StoredInspection(
        inspection_id=inspection_id, fabric_image_id=fabric_image_id, storage_key=storage_key
    )
