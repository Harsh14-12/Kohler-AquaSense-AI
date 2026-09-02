"""Fault management for the simulator."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from uuid import uuid4


SEVERITY_FACTORS = {
    "low": 1.25,
    "medium": 1.75,
    "high": 2.50,
}

SUPPORTED_FAULTS = {
    "continuous_leak",
    "ghost_flush",
    "sensor_dropout",
    "occupancy_spike",
    "abnormal_flow",
}


@dataclass(frozen=True)
class FaultEvent:
    fault_id: str
    fault_type: str
    start_time: datetime
    end_time: datetime
    severity: str
    fixture_id: str | None = None
    sensor_id: str | None = None
    zone_id: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def severity_factor(self) -> float:
        return SEVERITY_FACTORS[self.severity]

    def is_active(self, timestamp: datetime) -> bool:
        return self.start_time <= timestamp < self.end_time

    def applies_to_fixture(self, fixture_id: str) -> bool:
        return self.fixture_id == fixture_id

    def applies_to_sensor(self, sensor_id: str) -> bool:
        return self.sensor_id == sensor_id

    def applies_to_zone(self, zone_id: str) -> bool:
        return self.zone_id == zone_id


class FaultInjector:
    """Track scheduled and active simulator faults."""

    def __init__(self) -> None:
        self._faults: list[FaultEvent] = []

    def inject_fault(
        self,
        fault_type: str,
        duration_minutes: int,
        severity: str,
        start_time: datetime,
        fixture_id: str | None = None,
        sensor_id: str | None = None,
        zone_id: str | None = None,
    ) -> FaultEvent:
        """Create a scheduled fault event."""

        if fault_type not in SUPPORTED_FAULTS:
            raise ValueError(f"Unsupported fault type: {fault_type}")
        if severity not in SEVERITY_FACTORS:
            raise ValueError(f"Unsupported severity: {severity}")
        if duration_minutes <= 0:
            raise ValueError("duration_minutes must be positive")

        fault = FaultEvent(
            fault_id=str(uuid4()),
            fault_type=fault_type,
            start_time=start_time,
            end_time=start_time + timedelta(minutes=duration_minutes),
            severity=severity,
            fixture_id=fixture_id,
            sensor_id=sensor_id,
            zone_id=zone_id,
        )
        self._faults.append(fault)
        return fault

    def get_active_faults(self, timestamp: datetime) -> list[FaultEvent]:
        """Return faults active at the provided timestamp."""

        return [fault for fault in self._faults if fault.is_active(timestamp)]

    def list_faults(self) -> list[FaultEvent]:
        """Return all scheduled faults."""

        return list(self._faults)
