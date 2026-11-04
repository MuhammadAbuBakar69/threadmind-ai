"""Telemetry ingestion.

The ingest path is where bad data either enters the platform or is stopped. Two properties matter:

**Validation is shared.** The same `industrial.telemetry` contract validates simulator output and
gateway traffic. A simulator that bypasses the production validator proves nothing about production.

**Storage is idempotent.** MQTT QoS 1 is at-least-once, so the same reading arrives twice as a
matter of course. Insertion conflicts on the natural key `(machine_id, sensor_id, timestamp)` and
reports duplicates separately, so a redelivery burst is visible in the metrics rather than silently
inflating every window statistic derived from it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import text
from sqlalchemy.orm import Session

from industrial.telemetry import TelemetryReading, ValidationOutcome, validate_batch

INSERT_SQL = text(
    """
    INSERT INTO sensor_readings
        (organization_id, machine_id, sensor_id, "timestamp", numeric_value, quality_flag)
    VALUES
        (:organization_id, :machine_id, :sensor_id, :timestamp, :value, :quality_flag)
    ON CONFLICT (machine_id, sensor_id, "timestamp") DO NOTHING
    """
)


@dataclass(frozen=True)
class IngestResult:
    accepted: int
    duplicates: int
    rejected: list[dict[str, str]]

    @property
    def rejection_rate(self) -> float:
        total = self.accepted + self.duplicates + len(self.rejected)
        return 0.0 if total == 0 else len(self.rejected) / total


class TelemetryRepository(Protocol):
    def insert_many(self, readings: list[TelemetryReading]) -> tuple[int, int]:
        """Return (inserted, duplicates)."""
        ...


class SqlTelemetryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def insert_many(self, readings: list[TelemetryReading]) -> tuple[int, int]:
        inserted = 0
        for reading in readings:
            result = self._session.execute(
                INSERT_SQL,
                {
                    "organization_id": str(reading.organization_id),
                    "machine_id": str(reading.machine_id),
                    "sensor_id": str(reading.sensor_id),
                    "timestamp": reading.timestamp,
                    "value": reading.value,
                    "quality_flag": reading.quality_flag.value,
                },
            )
            inserted += 1 if result.rowcount else 0
        return inserted, len(readings) - inserted


class InMemoryTelemetryRepository:
    """Used by tests and by the simulator dry-run. Never in production."""

    def __init__(self) -> None:
        self.rows: dict[tuple[str, str, datetime], TelemetryReading] = {}

    def insert_many(self, readings: list[TelemetryReading]) -> tuple[int, int]:
        inserted = 0
        for reading in readings:
            key = (str(reading.machine_id), str(reading.sensor_id), reading.timestamp)
            if key in self.rows:
                continue
            self.rows[key] = reading
            inserted += 1
        return inserted, len(readings) - inserted


def ingest(
    readings: list[TelemetryReading],
    repository: TelemetryRepository,
    now: datetime | None = None,
) -> IngestResult:
    outcome: ValidationOutcome = validate_batch(readings, now=now or datetime.now(UTC))

    if not outcome.accepted:
        return IngestResult(accepted=0, duplicates=0, rejected=outcome.rejected)

    inserted, duplicates = repository.insert_many(outcome.accepted)
    return IngestResult(accepted=inserted, duplicates=duplicates, rejected=outcome.rejected)
