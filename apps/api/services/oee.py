"""Overall Equipment Effectiveness.

OEE is the number everyone in a factory argues about, so it must be computable the same way twice.
Three explicit definitions, one product:

    availability = run_time / planned_production_time
    performance  = (ideal_cycle_time * units_produced) / run_time
    quality      = good_units / units_produced
    oee          = availability * performance * quality

Two decisions worth defending:

* Inputs that cannot be true raise instead of being clipped. A run time longer than the planned
  time means the inputs are wrong, and a dashboard that silently reports 100% availability hides
  the sensor or shift-record problem that produced it.
* Performance may exceed 1.0 in raw terms (ideal cycle times are often optimistic). It is clamped
  for the OEE product and the raw value is preserved, so the anomaly stays visible instead of being
  averaged away.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OeeInputs:
    planned_production_time_minutes: float
    run_time_minutes: float
    ideal_cycle_time_seconds: float
    units_produced: int
    good_units: int
    downtime_minutes: float = 0.0


@dataclass(frozen=True)
class OeeResult:
    availability: float
    performance: float
    performance_raw: float
    quality: float
    oee: float
    clamped: bool

    def as_dict(self) -> dict[str, float | bool]:
        return {
            "availability": round(self.availability, 4),
            "performance": round(self.performance, 4),
            "performance_raw": round(self.performance_raw, 4),
            "quality": round(self.quality, 4),
            "oee": round(self.oee, 4),
            "clamped": self.clamped,
        }


class InvalidOeeInput(ValueError):
    pass


def compute_oee(inputs: OeeInputs) -> OeeResult:
    if inputs.planned_production_time_minutes <= 0:
        raise InvalidOeeInput("planned_production_time_minutes must be positive")
    if inputs.run_time_minutes < 0:
        raise InvalidOeeInput("run_time_minutes cannot be negative")
    if inputs.run_time_minutes > inputs.planned_production_time_minutes:
        raise InvalidOeeInput("run_time_minutes exceeds planned_production_time_minutes")
    if inputs.ideal_cycle_time_seconds <= 0:
        raise InvalidOeeInput("ideal_cycle_time_seconds must be positive")
    if inputs.units_produced < 0 or inputs.good_units < 0:
        raise InvalidOeeInput("unit counts cannot be negative")
    if inputs.good_units > inputs.units_produced:
        raise InvalidOeeInput("good_units cannot exceed units_produced")

    availability = inputs.run_time_minutes / inputs.planned_production_time_minutes

    if inputs.run_time_minutes == 0:
        # No running time means no output; performance and quality are undefined, not zero.
        return OeeResult(0.0, 0.0, 0.0, 0.0, 0.0, clamped=False)

    performance_raw = (inputs.ideal_cycle_time_seconds * inputs.units_produced) / (
        inputs.run_time_minutes * 60
    )
    quality = inputs.good_units / inputs.units_produced if inputs.units_produced else 0.0

    clamped = performance_raw > 1.0
    performance = min(performance_raw, 1.0)

    return OeeResult(
        availability=availability,
        performance=performance,
        performance_raw=performance_raw,
        quality=quality,
        oee=availability * performance * quality,
        clamped=clamped,
    )
