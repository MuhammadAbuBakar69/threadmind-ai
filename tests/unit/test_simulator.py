"""Simulator tests.

The simulator is research infrastructure, so the properties that matter are reproducibility and
honest labelling: same configuration in, same bytes out; every fault carries a ground-truth window;
and the corruptions it injects are actually rejected by the production validator.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from simulator import (
    Corruptions,
    Scenario,
    SimulationConfig,
    generate,
    ground_truth,
    write_dataset,
)

from industrial.telemetry import SensorType, validate_batch

START = datetime(2026, 11, 4, 8, 0, tzinfo=UTC)


def config(**overrides) -> SimulationConfig:
    base = {
        "machine_id": uuid.UUID("22222222-2222-4222-8222-222222222222"),
        "organization_id": uuid.UUID("11111111-1111-4111-8111-111111111111"),
        "sensor_ids": {sensor: uuid.UUID(int=index + 1) for index, sensor in enumerate(SensorType)},
        "scenario": Scenario.NORMAL,
        "seed": 42,
        "start": START,
        "duration_minutes": 60,
        "interval_seconds": 60,
    }
    base.update(overrides)
    return SimulationConfig(**base)


def test_same_config_produces_identical_output():
    """Without this, no experiment result can be re-run, and an unrepeatable result is an anecdote."""
    first = [r.to_jsonl() for r in generate(config())]
    second = [r.to_jsonl() for r in generate(config())]
    assert first == second


def test_different_seed_produces_different_output():
    a = [r.to_jsonl() for r in generate(config(seed=1))]
    b = [r.to_jsonl() for r in generate(config(seed=2))]
    assert a != b


def test_config_hash_is_stable_and_sensitive():
    assert config().config_hash() == config().config_hash()
    assert config().config_hash() != config(seed=7).config_hash()


def test_every_sensor_is_present():
    readings = generate(config())
    assert {r.telemetry.sensor_type for r in readings} == set(SensorType)


def test_fault_window_is_labelled():
    readings = generate(config(scenario=Scenario.BEARING_DEGRADATION))
    labelled = [r for r in readings if r.fault_active]
    assert labelled, "degradation scenario must mark a fault window"

    start, end = config().fault_start_minutes, config().fault_end_minutes
    for reading in labelled:
        minute = (reading.telemetry.timestamp - START).total_seconds() / 60
        assert start <= minute < end

    truth = ground_truth(config(scenario=Scenario.BEARING_DEGRADATION))
    assert truth["fault_start"] < truth["fault_end"]


def test_degradation_raises_vibration_above_normal_baseline():
    normal = [
        r.telemetry.value
        for r in generate(config())
        if r.telemetry.sensor_type is SensorType.VIBRATION and not r.fault_active
    ]
    degraded = [
        r.telemetry.value
        for r in generate(config(scenario=Scenario.BEARING_DEGRADATION))
        if r.telemetry.sensor_type is SensorType.VIBRATION
        and r.fault_active
        and Corruptions.OUT_OF_RANGE not in r.corruptions
    ]
    assert sum(degraded) / len(degraded) > sum(normal) / len(normal) * 2


def test_cooling_failure_raises_temperature_not_vibration():
    readings = generate(config(scenario=Scenario.COOLING_FAILURE))
    fault = [
        r for r in readings if r.fault_active and Corruptions.OUT_OF_RANGE not in r.corruptions
    ]
    temp = [r.telemetry.value for r in fault if r.telemetry.sensor_type is SensorType.TEMPERATURE]
    vib = [r.telemetry.value for r in fault if r.telemetry.sensor_type is SensorType.VIBRATION]
    assert max(temp) > 100
    assert max(vib) < 10


def test_corruptions_are_injected():
    readings = generate(
        config(missing_rate=0.05, duplicate_rate=0.05, delayed_rate=0.05, out_of_range_rate=0.05)
    )
    kinds = {c for r in readings for c in r.corruptions}
    assert Corruptions.DUPLICATE in kinds
    assert Corruptions.DELAYED in kinds
    assert Corruptions.OUT_OF_RANGE in kinds


def test_missing_readings_leave_a_gap_rather_than_a_zero():
    readings = generate(config(missing_rate=0.2))
    values = [
        r.telemetry.value for r in readings if r.telemetry.sensor_type is SensorType.TEMPERATURE
    ]
    assert 0.0 not in values


def test_injected_out_of_range_values_are_rejected_by_the_production_validator():
    """The whole point of injecting corruption: prove the ingest path catches it."""
    readings = [
        r
        for r in generate(config(out_of_range_rate=0.05))
        if Corruptions.DUPLICATE not in r.corruptions
    ]
    assert any(Corruptions.OUT_OF_RANGE in r.corruptions for r in readings)

    # Validate from the *end* of the simulation window: from the start, every later reading looks
    # like it arrived from the future and the freshness check masks the range check.
    end_of_window = START + timedelta(minutes=61)
    outcome = validate_batch([r.telemetry for r in readings], now=end_of_window)
    assert outcome.rejected
    assert all("outside plausible range" in item["reason"] for item in outcome.rejected)


def test_duplicate_event_ids_are_rejected_by_the_production_validator():
    readings = generate(config(duplicate_rate=0.2))
    outcome = validate_batch([r.telemetry for r in readings], now=START)
    assert any("duplicate event_id" in item["reason"] for item in outcome.rejected)


def test_delayed_readings_carry_suspect_quality():
    readings = generate(config(delayed_rate=0.2))
    delayed = [r for r in readings if Corruptions.DELAYED in r.corruptions]
    assert delayed
    assert all(r.telemetry.quality_flag.value == "suspect" for r in delayed)


def test_downtime_windows_mark_maintenance_state():
    readings = generate(config(downtime_windows=((10, 20),)))
    in_window = [
        r for r in readings if 10 <= (r.telemetry.timestamp - START).total_seconds() / 60 < 20
    ]
    assert in_window
    assert all(r.telemetry.machine_state.value == "maintenance" for r in in_window)


@pytest.mark.parametrize(
    "overrides",
    [
        {"fault_start_minutes": 50, "fault_end_minutes": 30},
        {"fault_end_minutes": 90},
        {"interval_seconds": 0},
        {"duration_minutes": 0},
        {"missing_rate": 1.0},
    ],
)
def test_invalid_configuration_is_rejected(overrides):
    with pytest.raises(ValueError):
        config(**overrides)


def test_write_dataset_produces_reproducible_artifacts(tmp_path):
    outputs = write_dataset(config(scenario=Scenario.OVERLOAD), tmp_path / "run")
    assert set(outputs) == {"readings", "ground_truth", "config"}

    lines = outputs["readings"].read_text().strip().splitlines()
    assert lines
    first = json.loads(lines[0])
    assert first["ground_truth"]["scenario"] == Scenario.OVERLOAD.value
    assert "fault_active" in first["ground_truth"]

    truth = json.loads(outputs["ground_truth"].read_text())
    assert truth["config_hash"] == config(scenario=Scenario.OVERLOAD).config_hash()
    assert "not evidence" in truth["note"]
