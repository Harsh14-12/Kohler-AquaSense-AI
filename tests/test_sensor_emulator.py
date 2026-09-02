from __future__ import annotations

import random
from datetime import datetime, timezone

from simulator.facility_topology import build_facility_topology
from simulator.sensor_emulator import SensorEmulator


def test_readings_have_expected_shape():
    topology = build_facility_topology("hospital")
    emulator = SensorEmulator()
    readings = emulator.generate_tick_readings(
        timestamp=datetime(2026, 1, 7, 9, 0, tzinfo=timezone.utc),
        topology=topology,
        occupancy_by_zone={zone.zone_id: 8 for zone in topology.zones},
        active_faults=[],
        rng=random.Random(1),
    )
    assert len(readings) == len(topology.sensors)
    assert all(reading.metadata["zone_type"] for reading in readings)


def test_flow_values_are_reasonable():
    topology = build_facility_topology("airport")
    emulator = SensorEmulator()
    readings = emulator.generate_tick_readings(
        timestamp=datetime(2026, 1, 7, 8, 0, tzinfo=timezone.utc),
        topology=topology,
        occupancy_by_zone={zone.zone_id: 12 for zone in topology.zones},
        active_faults=[],
        rng=random.Random(2),
    )
    flow_values = [reading.value for reading in readings if reading.sensor_type == "flow_meter"]
    assert flow_values
    assert min(flow_values) >= 0
    assert max(flow_values) < 15


def test_flush_counters_are_discrete():
    topology = build_facility_topology("airport")
    emulator = SensorEmulator()
    readings = emulator.generate_tick_readings(
        timestamp=datetime(2026, 1, 7, 8, 0, tzinfo=timezone.utc),
        topology=topology,
        occupancy_by_zone={zone.zone_id: 20 for zone in topology.zones},
        active_faults=[],
        rng=random.Random(4),
    )
    flush_values = [reading.value for reading in readings if reading.sensor_type == "flush_counter"]
    assert flush_values
    assert all(value.is_integer() for value in flush_values)


def test_diagnostics_use_valid_statuses():
    topology = build_facility_topology("university")
    emulator = SensorEmulator()
    readings = emulator.generate_tick_readings(
        timestamp=datetime(2026, 1, 7, 12, 0, tzinfo=timezone.utc),
        topology=topology,
        occupancy_by_zone={zone.zone_id: 5 for zone in topology.zones},
        active_faults=[],
        rng=random.Random(8),
    )
    statuses = {
        reading.diagnostic_status
        for reading in readings
        if reading.sensor_type == "diagnostic"
    }
    assert statuses <= {"ok", "degraded", "offline", "battery_low"}
