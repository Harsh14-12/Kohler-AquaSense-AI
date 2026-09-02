"""Generate realistic synthetic telemetry from topology and occupancy."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime

from schemas.telemetry import DiagnosticStatus, QualityFlag, SensorReading, SensorType, Unit

from .facility_topology import FacilityTopology, FixtureDefinition, SensorDefinition, ZoneDefinition
from .fault_injector import FaultEvent


DIAGNOSTIC_CODES = {
    DiagnosticStatus.OK.value: 0.0,
    DiagnosticStatus.DEGRADED.value: 1.0,
    DiagnosticStatus.BATTERY_LOW.value: 2.0,
    DiagnosticStatus.OFFLINE.value: 3.0,
}


@dataclass
class FixtureRuntimeState:
    active_flow: float = 0.0
    flush_total: int = 0
    last_values: dict[str, float] = field(default_factory=dict)


FIXTURE_BEHAVIOR = {
    "faucet": {"baseline": 0.02, "event_factor": 0.40, "burst": (1.2, 3.8), "decay": 0.25},
    "flush_valve": {"baseline": 0.00, "event_factor": 0.18, "burst": (6.0, 8.5), "decay": 0.05},
    "urinal": {"baseline": 0.00, "event_factor": 0.12, "burst": (2.5, 4.2), "decay": 0.08},
    "water_line": {"baseline": 0.18, "event_factor": 0.05, "burst": (0.4, 0.9), "decay": 0.68},
}


class SensorEmulator:
    """Stateful telemetry emulator."""

    def __init__(self) -> None:
        self._fixture_state: dict[str, FixtureRuntimeState] = {}

    def generate_tick_readings(
        self,
        timestamp: datetime,
        topology: FacilityTopology,
        occupancy_by_zone: dict[str, int],
        active_faults: list[FaultEvent],
        rng: random.Random,
    ) -> list[SensorReading]:
        """Generate one tick of telemetry for all sensors."""

        readings: list[SensorReading] = []

        for sensor in topology.sensors:
            fixture = topology.fixture_map[sensor.fixture_id]
            zone = topology.zone_map[sensor.zone_id]
            status = self._choose_diagnostic_status(sensor, active_faults, rng)
            quality_flag = QualityFlag.VALID.value

            if sensor.sensor_type == SensorType.FLOW_METER.value:
                value = self._generate_flow_value(
                    fixture=fixture,
                    zone=zone,
                    occupancy=occupancy_by_zone[zone.zone_id],
                    active_faults=active_faults,
                    rng=rng,
                )
            elif sensor.sensor_type == SensorType.FLUSH_COUNTER.value:
                value = self._generate_flush_value(
                    fixture=fixture,
                    zone=zone,
                    occupancy=occupancy_by_zone[zone.zone_id],
                    active_faults=active_faults,
                    rng=rng,
                )
            elif sensor.sensor_type == SensorType.OCCUPANCY_PIR.value:
                value = float(occupancy_by_zone[zone.zone_id])
            else:
                value = DIAGNOSTIC_CODES[status]

            if self._has_sensor_dropout(sensor.sensor_id, active_faults):
                quality_flag = QualityFlag.STALE.value
                status = DiagnosticStatus.OFFLINE.value
                value = self._fixture_state.setdefault(
                    fixture.fixture_id, FixtureRuntimeState()
                ).last_values.get(sensor.sensor_id, 0.0)

            reading = SensorReading(
                sensor_id=sensor.sensor_id,
                fixture_id=sensor.fixture_id,
                zone_id=sensor.zone_id,
                facility_id=sensor.facility_id,
                timestamp=timestamp,
                sensor_type=sensor.sensor_type,
                value=float(value),
                unit=sensor.unit,
                diagnostic_status=status,
                quality_flag=quality_flag,
                metadata={
                    "fixture_type": fixture.fixture_type,
                    "zone_type": zone.zone_type,
                    "occupancy": occupancy_by_zone[zone.zone_id],
                    "faults": self._fault_names_for_sensor(sensor, zone, active_faults),
                },
            )
            self._fixture_state.setdefault(fixture.fixture_id, FixtureRuntimeState()).last_values[
                sensor.sensor_id
            ] = float(reading.value)
            readings.append(reading)

        return readings

    def _generate_flow_value(
        self,
        fixture: FixtureDefinition,
        zone: ZoneDefinition,
        occupancy: int,
        active_faults: list[FaultEvent],
        rng: random.Random,
    ) -> float:
        state = self._fixture_state.setdefault(fixture.fixture_id, FixtureRuntimeState())
        behavior = FIXTURE_BEHAVIOR[fixture.fixture_type]
        activity_ratio = occupancy / max(1, zone.capacity)
        event_probability = min(0.95, behavior["event_factor"] * activity_ratio)
        if rng.random() < event_probability:
            burst_low, burst_high = behavior["burst"]
            state.active_flow = rng.uniform(burst_low, burst_high)
        else:
            state.active_flow *= behavior["decay"]

        occupancy_contribution = 0.0
        if fixture.fixture_type == "water_line":
            occupancy_contribution = activity_ratio * 1.6

        flow = behavior["baseline"] + state.active_flow + occupancy_contribution
        flow += rng.uniform(-0.05, 0.05)

        for fault in active_faults:
            if fault.fault_type == "continuous_leak" and fault.applies_to_fixture(fixture.fixture_id):
                flow = max(flow, 1.4 * fault.severity_factor)
            if fault.fault_type == "abnormal_flow" and fault.applies_to_fixture(fixture.fixture_id):
                flow *= fault.severity_factor

        return round(max(0.0, flow), 3)

    def _generate_flush_value(
        self,
        fixture: FixtureDefinition,
        zone: ZoneDefinition,
        occupancy: int,
        active_faults: list[FaultEvent],
        rng: random.Random,
    ) -> float:
        state = self._fixture_state.setdefault(fixture.fixture_id, FixtureRuntimeState())
        activity_ratio = occupancy / max(1, zone.capacity)
        flush_probability = 0.05 + (0.35 * activity_ratio)

        if rng.random() < flush_probability:
            state.flush_total += 1

        for fault in active_faults:
            if fault.fault_type == "ghost_flush" and fault.applies_to_fixture(fixture.fixture_id):
                extra_flushes = max(1, int(round(fault.severity_factor - 0.5)))
                state.flush_total += extra_flushes

        return float(state.flush_total)

    def _choose_diagnostic_status(
        self,
        sensor: SensorDefinition,
        active_faults: list[FaultEvent],
        rng: random.Random,
    ) -> str:
        if self._has_sensor_dropout(sensor.sensor_id, active_faults):
            return DiagnosticStatus.OFFLINE.value

        roll = rng.random()
        if roll < 0.992:
            return DiagnosticStatus.OK.value
        if roll < 0.996:
            return DiagnosticStatus.DEGRADED.value
        if roll < 0.999:
            return DiagnosticStatus.BATTERY_LOW.value
        return DiagnosticStatus.OFFLINE.value

    @staticmethod
    def _has_sensor_dropout(sensor_id: str, active_faults: list[FaultEvent]) -> bool:
        return any(
            fault.fault_type == "sensor_dropout" and fault.applies_to_sensor(sensor_id)
            for fault in active_faults
        )

    @staticmethod
    def _fault_names_for_sensor(
        sensor: SensorDefinition,
        zone: ZoneDefinition,
        active_faults: list[FaultEvent],
    ) -> list[str]:
        return [
            fault.fault_type
            for fault in active_faults
            if fault.applies_to_sensor(sensor.sensor_id)
            or fault.applies_to_fixture(sensor.fixture_id)
            or fault.applies_to_zone(zone.zone_id)
        ]
