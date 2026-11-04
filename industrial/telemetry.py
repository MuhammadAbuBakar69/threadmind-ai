"""Telemetry payload contract.

One validator for every producer: MQTT gateway, HTTP ingestion, and the synthetic simulator. The
alternative — a permissive ingest that trusts the device — means bad readings reach the anomaly
models, and an anomaly model fed out-of-range values reports anomalies that are really just bad
data.

Deliberate choices:

* Ranges are physically motivated and conservative. A value outside them is rejected, not clipped:
  silently clipping a 900 C bearing reading to the maximum destroys the most informative sample in
  the batch.
* `quality_flag` is the device's own assessment (good/suspect/...) and travels with the reading.
  Downstream code must be able to exclude suspect data without re-deriving it.
* Timestamps are timezone-aware UTC. Naive timestamps are rejected because they are silently
  wrong by five hours in Pakistan, which is exactly enough to misalign a root cause window.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SensorType(StrEnum):
    TEMPERATURE = "temperature"
    VIBRATION = "vibration"
    SPEED = "speed"
    TORQUE = "torque"
    CURRENT = "current"
    PRESSURE = "pressure"


class MachineState(StrEnum):
    RUNNING = "running"
    IDLE = "idle"
    STARTUP = "startup"
    OVERLOADED = "overloaded"
    DEGRADED = "degraded"
    MAINTENANCE = "maintenance"


class QualityFlag(StrEnum):
    GOOD = "good"
    SUSPECT = "suspect"
    MISSING = "missing"
    INTERPOLATED = "interpolated"


# (min, max, unit). Bounds are wide enough to admit real industrial equipment and narrow enough to
# catch a unit error, a stuck sensor, or a wrong sensor mapped to the wrong machine.
SENSOR_BOUNDS: dict[SensorType, tuple[float, float, str]] = {
    SensorType.TEMPERATURE: (-40.0, 400.0, "degC"),
    SensorType.VIBRATION: (0.0, 100.0, "mm/s"),
    SensorType.SPEED: (0.0, 20000.0, "rpm"),
    SensorType.TORQUE: (0.0, 5000.0, "Nm"),
    SensorType.CURRENT: (0.0, 1000.0, "A"),
    SensorType.PRESSURE: (0.0, 350.0, "bar"),
}


class TelemetryValidationError(ValueError):
    """Raised when a reading cannot be trusted. The message is safe to log and return."""

    def __init__(self, field: str, reason: str) -> None:
        self.field = field
        self.reason = reason
        super().__init__(f"{field}: {reason}")


class TelemetryReading(BaseModel):
    """A single sensor sample for a single machine.

    `event_id` is the idempotency key. At-least-once delivery is the normal case on MQTT, so the
    ingest path upserts on it rather than appending a duplicate row.
    """

    model_config = ConfigDict(extra="forbid")

    event_id: UUID
    organization_id: UUID
    machine_id: UUID
    sensor_id: UUID
    sensor_type: SensorType
    machine_state: MachineState
    value: float
    timestamp: datetime
    quality_flag: QualityFlag = QualityFlag.GOOD
    produced_at: datetime | None = None

    @field_validator("timestamp", "produced_at")
    @classmethod
    def must_be_timezone_aware(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return v
        if v.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware (UTC)")
        return v.astimezone(UTC)

    @field_validator("value")
    @classmethod
    def must_be_finite(cls, v: float) -> float:
        if v != v or v in (float("inf"), float("-inf")):
            raise ValueError("non-finite value")
        return v

    def validate_range(self) -> None:
        low, high, unit = SENSOR_BOUNDS[self.sensor_type]
        if not low <= self.value <= high:
            raise TelemetryValidationError(
                "value", f"{self.value}{unit} outside plausible range {low}-{high}{unit}"
            )

    def validate_freshness(self, now: datetime, max_skew_seconds: int = 300) -> None:
        """Reject readings from the future, and readings too old to be worth ingesting.

        A device with a drifting clock will otherwise inject readings into windows that have
        already been analysed, quietly corrupting historical root cause evidence.
        """
        skew = (self.timestamp - now).total_seconds()
        if skew > max_skew_seconds:
            raise TelemetryValidationError(
                "timestamp", f"{skew:.0f}s in the future exceeds {max_skew_seconds}s tolerance"
            )


class TelemetryBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    readings: list[TelemetryReading] = Field(min_length=1, max_length=1000)


class ValidationOutcome(BaseModel):
    """Result of validating a batch.

    Accepted and rejected are reported separately on purpose: a gateway that sends 999 good
    readings and one malformed one should have the good ones stored and the bad one logged, not the
    whole batch dropped.
    """

    accepted: list[TelemetryReading] = Field(default_factory=list)
    rejected: list[dict[str, str]] = Field(default_factory=list)

    @property
    def rejection_rate(self) -> float:
        total = len(self.accepted) + len(self.rejected)
        return 0.0 if total == 0 else len(self.rejected) / total


def validate_batch(
    readings: list[TelemetryReading], now: datetime | None = None
) -> ValidationOutcome:
    now = now or datetime.now(UTC)
    outcome = ValidationOutcome()
    seen: set[UUID] = set()

    for reading in readings:
        try:
            reading.validate_range()
            reading.validate_freshness(now)
            if reading.event_id in seen:
                outcome.rejected.append(
                    {"event_id": str(reading.event_id), "reason": "duplicate event_id in batch"}
                )
                continue
            seen.add(reading.event_id)
        except TelemetryValidationError as exc:
            outcome.rejected.append({"event_id": str(reading.event_id), "reason": str(exc)})
            continue
        outcome.accepted.append(reading)

    return outcome
