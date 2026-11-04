"""Telemetry contract tests.

These protect the boundary where bad device data is stopped. Every assertion here corresponds to a
failure mode observed in real industrial ingestion: unit errors, stuck sensors, drifting clocks,
naive timestamps, and at-least-once redelivery.
"""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from industrial.telemetry import (
    MachineState,
    QualityFlag,
    SensorType,
    TelemetryReading,
    TelemetryValidationError,
    validate_batch,
)

NOW = datetime(2026, 11, 4, 9, 30, tzinfo=UTC)


def reading(**overrides) -> TelemetryReading:
    base = {
        "event_id": uuid.uuid4(),
        "organization_id": uuid.uuid4(),
        "machine_id": uuid.uuid4(),
        "sensor_id": uuid.uuid4(),
        "sensor_type": SensorType.VIBRATION,
        "machine_state": MachineState.RUNNING,
        "value": 3.1,
        "timestamp": NOW - timedelta(seconds=30),
        "quality_flag": QualityFlag.GOOD,
    }
    base.update(overrides)
    return TelemetryReading(**base)


def test_plausible_reading_passes():
    validate_batch([reading()], now=NOW)


def test_naive_timestamp_is_rejected():
    with pytest.raises(ValidationError):
        reading(timestamp=datetime(2026, 11, 4, 9, 30))


def test_non_finite_value_is_rejected():
    for bad in (math.nan, math.inf, -math.inf):
        with pytest.raises(ValidationError):
            reading(value=bad)


def test_value_outside_physical_range_is_rejected_not_clipped():
    outcome = validate_batch([reading(value=950.0)], now=NOW)
    assert outcome.accepted == []
    assert outcome.rejected[0]["event_id"]
    assert "outside plausible range" in outcome.rejected[0]["reason"]


def test_unit_error_is_caught():
    """A torque reported in Nmm instead of Nm lands an order of magnitude out of range."""
    outcome = validate_batch([reading(sensor_type=SensorType.TORQUE, value=180000.0)], now=NOW)
    assert outcome.rejected


def test_future_timestamp_beyond_skew_is_rejected():
    outcome = validate_batch([reading(timestamp=NOW + timedelta(minutes=30))], now=NOW)
    assert outcome.rejected
    assert "future" in outcome.rejected[0]["reason"]


def test_small_clock_skew_is_tolerated():
    validate_batch([reading(timestamp=NOW + timedelta(seconds=5))], now=NOW)


def test_duplicate_event_id_within_batch_is_reported_once():
    shared = uuid.uuid4()
    outcome = validate_batch([reading(event_id=shared), reading(event_id=shared)], now=NOW)
    assert len(outcome.accepted) == 1
    assert "duplicate event_id" in outcome.rejected[0]["reason"]


def test_partial_batch_keeps_the_good_readings():
    """One malformed sample must not cost the factory the other 99."""
    outcome = validate_batch([reading(), reading(value=1e9), reading()], now=NOW)
    assert len(outcome.accepted) == 2
    assert len(outcome.rejected) == 1
    assert outcome.rejection_rate == pytest.approx(1 / 3, rel=1e-6)


def test_unknown_field_is_rejected():
    """extra='forbid' stops a gateway's typo from being silently ignored."""
    with pytest.raises(ValidationError):
        TelemetryReading(
            event_id=uuid.uuid4(),
            organization_id=uuid.uuid4(),
            machine_id=uuid.uuid4(),
            sensor_id=uuid.uuid4(),
            sensor_type=SensorType.SPEED,
            machine_state=MachineState.RUNNING,
            value=1400.0,
            timestamp=NOW,
            unexpected_field="ignored?",
        )


def test_validate_range_raises_directly():
    with pytest.raises(TelemetryValidationError):
        reading(sensor_type=SensorType.PRESSURE, value=900.0).validate_range()
