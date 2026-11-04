"""Deterministic industrial telemetry simulator.

Purpose: let the ingest path, the anomaly models and the root cause window logic be developed and
tested before a factory grants access to a machine. Every reading carries ground truth, so a
detector can be scored against a known injection timestamp instead of against a guess.

Determinism is the requirement that shapes the whole module. Given the same `SimulationConfig`, the
output is byte-identical: same readings, same order, same injected faults, same corrupted samples.
Without that, an experiment cannot be re-run, and a result that cannot be re-run is an anecdote.

Documented limits (also in docs/research-reproducibility.md):

* These signals are plausible, not validated. A model that detects bearings in this data has
  detected a mathematical pattern someone wrote, not a textile machine.
* Faults are injected as clean parametric deviations. Real degradation is messier, arrives with
  confounders, and does not announce its start time.
* No result from synthetic data may be reported as evidence of predictive performance on real
  looms. It validates the pipeline, nothing more.
"""

from __future__ import annotations

import hashlib
import json
import random
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path

from industrial.telemetry import (
    SENSOR_BOUNDS,
    MachineState,
    QualityFlag,
    SensorType,
    TelemetryReading,
)


class Scenario(StrEnum):
    NORMAL = "normal"
    BEARING_DEGRADATION = "bearing_degradation"
    OVERLOAD = "overload"
    COOLING_FAILURE = "cooling_failure"
    MISALIGNMENT = "misalignment"
    SENSOR_FAILURE = "sensor_failure"


class Corruptions(StrEnum):
    """Faults in the *data path*, not the machine. These must be rejected by validation."""

    MISSING = "missing"
    DELAYED = "delayed"
    DUPLICATE = "duplicate"
    OUT_OF_RANGE = "out_of_range"


SCENARIO_NOTES: dict[Scenario, str] = {
    Scenario.NORMAL: "Steady production. Any alert here is a false positive.",
    Scenario.BEARING_DEGRADATION: "Vibration and temperature ramp over the fault window; energy rises.",
    Scenario.OVERLOAD: "Speed drops while current and torque climb: a starving or jammed process.",
    Scenario.COOLING_FAILURE: "Temperature climbs with vibration roughly stable, isolating thermal cause.",
    Scenario.MISALIGNMENT: "Vibration rises at a fixed offset with mild torque oscillation.",
    Scenario.SENSOR_FAILURE: "One sensor freezes then reports garbage: data fault masquerading as machine fault.",
}

# Baseline operating point per sensor for a healthy running machine.
BASELINE: dict[SensorType, float] = {
    SensorType.TEMPERATURE: 62.0,
    SensorType.VIBRATION: 2.4,
    SensorType.SPEED: 1450.0,
    SensorType.TORQUE: 180.0,
    SensorType.CURRENT: 42.0,
    SensorType.PRESSURE: 6.2,
}

# Relative noise amplitude per sensor (fraction of baseline).
NOISE: dict[SensorType, float] = {
    SensorType.TEMPERATURE: 0.012,
    SensorType.VIBRATION: 0.09,
    SensorType.SPEED: 0.008,
    SensorType.TORQUE: 0.05,
    SensorType.CURRENT: 0.04,
    SensorType.PRESSURE: 0.03,
}

# Multiplicative delta applied at full fault severity: (sensor -> multiplier added).
FAULT_EFFECTS: dict[Scenario, dict[SensorType, float]] = {
    Scenario.NORMAL: {},
    Scenario.BEARING_DEGRADATION: {
        SensorType.VIBRATION: 4.2,
        SensorType.TEMPERATURE: 0.55,
        SensorType.CURRENT: 0.18,
    },
    Scenario.OVERLOAD: {
        SensorType.CURRENT: 0.75,
        SensorType.TORQUE: 0.60,
        SensorType.SPEED: -0.18,
        SensorType.TEMPERATURE: 0.28,
    },
    Scenario.COOLING_FAILURE: {
        SensorType.TEMPERATURE: 0.95,
        SensorType.PRESSURE: 0.22,
    },
    Scenario.MISALIGNMENT: {
        SensorType.VIBRATION: 2.9,
        SensorType.TORQUE: 0.22,
    },
    Scenario.SENSOR_FAILURE: {},
}


@dataclass(frozen=True)
class SimulationConfig:
    machine_id: uuid.UUID
    organization_id: uuid.UUID
    sensor_ids: dict[SensorType, uuid.UUID]
    scenario: Scenario = Scenario.NORMAL
    seed: int = 42
    start: datetime = field(default_factory=lambda: datetime.now(UTC))
    duration_minutes: int = 60
    interval_seconds: int = 60
    # Fault window as offsets from `start`. Defaults put the fault past the midpoint so there is
    # enough healthy data to establish a baseline before the deviation begins.
    fault_start_minutes: int = 30
    fault_end_minutes: int = 50
    missing_rate: float = 0.01
    duplicate_rate: float = 0.005
    delayed_rate: float = 0.005
    out_of_range_rate: float = 0.002
    downtime_windows: tuple[tuple[int, int], ...] = ()

    def __post_init__(self) -> None:
        if self.interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        if self.duration_minutes <= 0:
            raise ValueError("duration_minutes must be positive")
        if not 0 <= self.fault_start_minutes < self.fault_end_minutes <= self.duration_minutes:
            raise ValueError("fault window must sit inside the simulation window")
        for name in ("missing_rate", "duplicate_rate", "delayed_rate", "out_of_range_rate"):
            if not 0.0 <= getattr(self, name) < 1.0:
                raise ValueError(f"{name} must be in [0, 1)")

    def config_hash(self) -> str:
        """Stable fingerprint recorded alongside any experiment that used this configuration."""
        payload = {
            "machine_id": str(self.machine_id),
            "organization_id": str(self.organization_id),
            "sensor_ids": {k.value: str(v) for k, v in sorted(self.sensor_ids.items())},
            "scenario": self.scenario.value,
            "seed": self.seed,
            "start": self.start.isoformat(),
            "duration_minutes": self.duration_minutes,
            "interval_seconds": self.interval_seconds,
            "fault_start_minutes": self.fault_start_minutes,
            "fault_end_minutes": self.fault_end_minutes,
            "missing_rate": self.missing_rate,
            "duplicate_rate": self.duplicate_rate,
            "delayed_rate": self.delayed_rate,
            "out_of_range_rate": self.out_of_range_rate,
            "downtime_windows": self.downtime_windows,
        }
        blob = json.dumps(payload, sort_keys=True).encode()
        return hashlib.sha256(blob).hexdigest()[:16]


@dataclass(frozen=True)
class SyntheticReading:
    """A simulated sample. `fault_active` is the label a detector is scored against."""

    telemetry: TelemetryReading
    fault_active: bool
    scenario: Scenario
    corruptions: tuple[Corruptions, ...] = ()

    def to_jsonl(self) -> str:
        return json.dumps(
            {
                "event_id": str(self.telemetry.event_id),
                "organization_id": str(self.telemetry.organization_id),
                "machine_id": str(self.telemetry.machine_id),
                "sensor_id": str(self.telemetry.sensor_id),
                "sensor_type": self.telemetry.sensor_type.value,
                "machine_state": self.telemetry.machine_state.value,
                "value": self.telemetry.value,
                "timestamp": self.telemetry.timestamp.isoformat(),
                "quality_flag": self.telemetry.quality_flag.value,
                "ground_truth": {
                    "scenario": self.scenario.value,
                    "fault_active": self.fault_active,
                    "corruptions": [c.value for c in self.corruptions],
                },
            },
            sort_keys=True,
        )


def _machine_state(config: SimulationConfig, minute: float) -> MachineState:
    for start, end in config.downtime_windows:
        if start <= minute < end:
            return MachineState.MAINTENANCE
    if config.scenario is Scenario.OVERLOAD and _in_fault(config, minute):
        return MachineState.OVERLOADED
    if config.scenario is not Scenario.NORMAL and _in_fault(config, minute):
        return MachineState.DEGRADED
    return MachineState.RUNNING


def _in_fault(config: SimulationConfig, minute: float) -> bool:
    return config.fault_start_minutes <= minute < config.fault_end_minutes


def _severity(config: SimulationConfig, minute: float) -> float:
    """Ramp from 0 to 1 across the fault window.

    A step change would make every detector look excellent, because the first deviation is also the
    largest one. A ramp is the harder and more honest shape.
    """
    if not _in_fault(config, minute):
        return 0.0
    span = config.fault_end_minutes - config.fault_start_minutes
    return min(1.0, (minute - config.fault_start_minutes) / span)


def _state_multiplier(state: MachineState) -> float:
    return {
        MachineState.RUNNING: 1.0,
        MachineState.IDLE: 0.18,
        MachineState.STARTUP: 1.15,
        MachineState.OVERLOADED: 1.25,
        MachineState.DEGRADED: 1.0,
        MachineState.MAINTENANCE: 0.0,
    }[state]


def generate(config: SimulationConfig) -> list[SyntheticReading]:
    """Generate the full reading sequence deterministically."""
    rng = random.Random(config.seed)
    readings: list[SyntheticReading] = []

    total_steps = int(config.duration_minutes * 60 / config.interval_seconds)
    effects = FAULT_EFFECTS[config.scenario]

    for step in range(total_steps):
        elapsed_seconds = step * config.interval_seconds
        timestamp = config.start + timedelta(seconds=elapsed_seconds)
        minute = elapsed_seconds / 60.0
        state = _machine_state(config, minute)
        severity = _severity(config, minute)
        in_fault = _in_fault(config, minute)

        for sensor_type, sensor_id in config.sensor_ids.items():
            value = BASELINE[sensor_type] * _state_multiplier(state)

            # Fault deviation, ramped by severity.
            if sensor_type in effects:
                value *= 1.0 + effects[sensor_type] * severity

            # Sensor failure: freeze, then report garbage.
            if config.scenario is Scenario.SENSOR_FAILURE and in_fault:
                if sensor_type is SensorType.VIBRATION and severity > 0.4:
                    value = SENSOR_BOUNDS[sensor_type][1] * 1.4  # impossible by design
                elif sensor_type is SensorType.TEMPERATURE and severity > 0.7:
                    value = BASELINE[sensor_type]  # frozen: zero variance, a real failure signature

            value += rng.gauss(0.0, NOISE[sensor_type] * max(abs(value), 1e-9))

            quality = QualityFlag.GOOD
            corruptions: list[Corruptions] = []
            event_id = uuid.UUID(int=rng.getrandbits(128))
            emit_timestamp = timestamp

            roll = rng.random()
            if roll < config.missing_rate:
                # A gap, not a zero: emitting 0.0 would be a lie the model would learn from.
                corruptions.append(Corruptions.MISSING)
                continue
            elif roll < config.missing_rate + config.delayed_rate:
                corruptions.append(Corruptions.DELAYED)
                emit_timestamp = timestamp + timedelta(seconds=rng.randint(30, 180))
                quality = QualityFlag.SUSPECT
            elif roll < config.missing_rate + config.delayed_rate + config.out_of_range_rate:
                corruptions.append(Corruptions.OUT_OF_RANGE)
                # Pin the value beyond the contract's upper bound rather than scaling it. Scaling
                # was quietly wrong: a 40x vibration reading of 96 mm/s still sat inside the valid
                # range, so for some sensors the injected "corruption" was perfectly acceptable and
                # the test that proves the validator catches it was vacuous.
                value = SENSOR_BOUNDS[sensor_type][1] * 1.5
                quality = QualityFlag.SUSPECT

            readings.append(
                SyntheticReading(
                    telemetry=TelemetryReading(
                        event_id=event_id,
                        organization_id=config.organization_id,
                        machine_id=config.machine_id,
                        sensor_id=sensor_id,
                        sensor_type=sensor_type,
                        machine_state=state,
                        value=round(value, 4),
                        timestamp=emit_timestamp,
                        quality_flag=quality,
                        produced_at=timestamp,
                    ),
                    fault_active=in_fault,
                    scenario=config.scenario,
                    corruptions=tuple(corruptions),
                )
            )

            # At-least-once delivery: the same event_id arrives twice.
            if rng.random() < config.duplicate_rate:
                readings.append(
                    SyntheticReading(
                        telemetry=readings[-1].telemetry.model_copy(
                            update={"quality_flag": QualityFlag.SUSPECT}
                        ),
                        fault_active=in_fault,
                        scenario=config.scenario,
                        corruptions=(*corruptions, Corruptions.DUPLICATE),
                    )
                )

    return readings


def ground_truth(config: SimulationConfig) -> dict[str, object]:
    """The label record for a simulation. This is what a detector is scored against."""
    return {
        "config_hash": config.config_hash(),
        "machine_id": str(config.machine_id),
        "organization_id": str(config.organization_id),
        "scenario": config.scenario.value,
        "scenario_note": SCENARIO_NOTES[config.scenario],
        "seed": config.seed,
        "start": config.start.isoformat(),
        "end": (config.start + timedelta(minutes=config.duration_minutes)).isoformat(),
        "fault_start": (config.start + timedelta(minutes=config.fault_start_minutes)).isoformat(),
        "fault_end": (config.start + timedelta(minutes=config.fault_end_minutes)).isoformat(),
        "interval_seconds": config.interval_seconds,
        "sensors": {k.value: str(v) for k, v in config.sensor_ids.items()},
        "note": (
            "Synthetic data. Validates pipeline and method only; it is not evidence of predictive "
            "performance on real textile machinery."
        ),
    }


def write_dataset(config: SimulationConfig, directory: Path) -> dict[str, Path]:
    """Write readings.jsonl + ground_truth.json + config.json for a reproducible experiment input."""
    directory.mkdir(parents=True, exist_ok=True)
    readings = generate(config)

    readings_path = directory / "readings.jsonl"
    with readings_path.open("w", encoding="utf-8") as fh:
        for reading in readings:
            fh.write(reading.to_jsonl() + "\n")

    truth_path = directory / "ground_truth.json"
    truth_path.write_text(json.dumps(ground_truth(config), indent=2), encoding="utf-8")

    config_path = directory / "simulation_config.json"
    config_path.write_text(
        json.dumps(
            {
                "scenario": config.scenario.value,
                "seed": config.seed,
                "duration_minutes": config.duration_minutes,
                "interval_seconds": config.interval_seconds,
                "corruption_rates": {
                    "missing": config.missing_rate,
                    "duplicate": config.duplicate_rate,
                    "delayed": config.delayed_rate,
                    "out_of_range": config.out_of_range_rate,
                },
                "config_hash": config.config_hash(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return {"readings": readings_path, "ground_truth": truth_path, "config": config_path}


def publish_mqtt(
    readings: list[SyntheticReading], broker_url: str, topic_prefix: str = "threadmind"
) -> int:
    """Publish to an MQTT broker. Requires paho-mqtt; not exercised by the test suite.

    Delivery is intentionally QoS 1 so the ingest path is tested against duplicate arrivals, which
    is what a real gateway will do.
    """
    try:
        import paho.mqtt.client as mqtt  # noqa: PLC0415 - optional dependency
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "paho-mqtt is required for MQTT publishing: pip install paho-mqtt"
        ) from exc

    client = mqtt.Client()
    client.connect(broker_url.replace("mqtt://", "").split(":")[0], 1883)
    client.loop_start()

    published = 0
    for reading in readings:
        topic = f"{topic_prefix}/{reading.telemetry.organization_id}/{reading.telemetry.machine_id}"
        info = client.publish(topic, reading.to_jsonl(), qos=1)
        info.wait_for_publish()
        published += 1

    client.loop_stop()
    client.disconnect()
    return published


def _demo_uuids() -> tuple[uuid.UUID, uuid.UUID, dict[SensorType, uuid.UUID]]:
    org = uuid.UUID("11111111-1111-4111-8111-111111111111")
    machine = uuid.UUID("22222222-2222-4222-8222-222222222222")
    sensors = {
        sensor: uuid.UUID(int=(index + 3) * 0x11111111111111111111111111111111 % (2**128))
        for index, sensor in enumerate(SensorType)
    }
    return org, machine, sensors


def main() -> None:  # pragma: no cover - CLI
    import argparse

    org, machine, sensors = _demo_uuids()
    parser = argparse.ArgumentParser(description="Generate deterministic synthetic telemetry.")
    parser.add_argument(
        "--scenario", choices=[s.value for s in Scenario], default=Scenario.NORMAL.value
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--minutes", type=int, default=60)
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument("--out", type=Path, default=Path("data/synthetic/run"))
    parser.add_argument(
        "--fault-start", type=int, default=None, help="minutes from start; default 50%% of duration"
    )
    parser.add_argument(
        "--fault-end", type=int, default=None, help="minutes from start; default 85%% of duration"
    )
    parser.add_argument(
        "--mqtt", default=None, help="mqtt://host:1883 to publish instead of writing files"
    )
    args = parser.parse_args()

    # Scale the fault window to the requested duration. The dataclass defaults assume an hour; a
    # 30-minute run would otherwise be rejected by its own validation, which is exactly the kind of
    # sharp edge that makes a research tool feel broken on first use.
    fault_start = args.fault_start if args.fault_start is not None else int(args.minutes * 0.50)
    fault_end = args.fault_end if args.fault_end is not None else int(args.minutes * 0.85)

    config = SimulationConfig(
        machine_id=machine,
        organization_id=org,
        sensor_ids=sensors,
        scenario=Scenario(args.scenario),
        seed=args.seed,
        duration_minutes=args.minutes,
        interval_seconds=args.interval,
        fault_start_minutes=max(1, fault_start),
        fault_end_minutes=max(max(1, fault_start) + 1, fault_end),
    )

    if args.mqtt:
        count = publish_mqtt(generate(config), args.mqtt)
        print(f"published {count} readings to {args.mqtt}")
        return

    outputs = write_dataset(config, args.out)
    readings = generate(config)
    faults = sum(1 for r in readings if r.fault_active)
    corrupt = sum(1 for r in readings if r.corruptions)
    print(f"config_hash : {config.config_hash()}")
    print(f"readings    : {len(readings)}  (fault window: {faults}, corrupted: {corrupt})")
    for name, path in outputs.items():
        print(f"{name:<12}: {path}")


if __name__ == "__main__":  # pragma: no cover
    main()
