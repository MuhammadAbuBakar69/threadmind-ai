"""OEE tests.

OEE is the number a factory argues about, so the definitions are pinned by tests rather than left to
each implementation. The important cases are the invalid ones: silently clipping bad inputs is how a
dashboard reports 100% availability on a line that was stopped.
"""

from __future__ import annotations

import pytest
from services.oee import InvalidOeeInput, OeeInputs, compute_oee


def test_textbook_example():
    result = compute_oee(
        OeeInputs(
            planned_production_time_minutes=480,
            run_time_minutes=400,
            ideal_cycle_time_seconds=30,
            units_produced=720,
            good_units=700,
            downtime_minutes=80,
        )
    )
    assert result.availability == pytest.approx(400 / 480)
    # 30s * 720 units = 360 min of ideal output against 400 min of run time -> 0.9
    assert result.performance == pytest.approx(0.9)
    assert result.quality == pytest.approx(700 / 720)
    assert result.oee == pytest.approx(result.availability * result.performance * result.quality)


def test_no_run_time_returns_zero_not_undefined_error():
    result = compute_oee(
        OeeInputs(
            planned_production_time_minutes=480,
            run_time_minutes=0,
            ideal_cycle_time_seconds=30,
            units_produced=0,
            good_units=0,
        )
    )
    assert result.oee == 0.0
    assert result.availability == 0.0


def test_performance_above_one_is_clamped_but_visible():
    """An optimistic ideal cycle time can push performance past 100%. Show it, do not hide it."""
    result = compute_oee(
        OeeInputs(
            planned_production_time_minutes=480,
            run_time_minutes=400,
            ideal_cycle_time_seconds=40,
            units_produced=700,
            good_units=700,
        )
    )
    assert result.performance_raw > 1.0
    assert result.performance == 1.0
    assert result.clamped is True


@pytest.mark.parametrize(
    "kwargs",
    [
        {"planned_production_time_minutes": 0},
        {"run_time_minutes": -1},
        {"run_time_minutes": 500},  # exceeds planned time
        {"ideal_cycle_time_seconds": 0},
        {"good_units": 900, "units_produced": 800},
        {"units_produced": -5, "good_units": 0},
    ],
)
def test_impossible_inputs_raise(kwargs):
    base = {
        "planned_production_time_minutes": 480,
        "run_time_minutes": 400,
        "ideal_cycle_time_seconds": 30,
        "units_produced": 800,
        "good_units": 750,
    }
    base.update(kwargs)
    with pytest.raises(InvalidOeeInput):
        compute_oee(OeeInputs(**base))


def test_zero_units_produced_treats_quality_as_zero():
    result = compute_oee(
        OeeInputs(
            planned_production_time_minutes=480,
            run_time_minutes=100,
            ideal_cycle_time_seconds=30,
            units_produced=0,
            good_units=0,
        )
    )
    assert result.quality == 0.0
