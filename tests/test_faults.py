from __future__ import annotations

from datetime import datetime, timezone

from simulator.simulation_engine import SimulationEngine


def test_continuous_leak_produces_sustained_flow(tmp_path):
    engine = SimulationEngine(
        preset_name="university",
        database_path=tmp_path / "test.db",
        start_time=datetime(2026, 1, 7, 2, 0, tzinfo=timezone.utc),
        seed=5,
    )
    fixture = engine.topology.fixtures[0]
    engine.inject_fault("continuous_leak", fixture_id=fixture.fixture_id, duration_minutes=30, severity="high")
    result = engine.run_tick(persist=False)
    target = next(
        reading
        for reading in result.readings
        if reading.fixture_id == fixture.fixture_id and reading.sensor_type == "flow_meter"
    )
    assert result.occupancy_by_zone[fixture.zone_id] == 0
    assert target.value >= 3.0


def test_ghost_flush_increments_counter_without_occupancy(tmp_path):
    engine = SimulationEngine(
        preset_name="university",
        database_path=tmp_path / "test.db",
        start_time=datetime(2026, 1, 7, 2, 0, tzinfo=timezone.utc),
        seed=11,
    )
    fixture = next(item for item in engine.topology.fixtures if item.fixture_type == "urinal")
    engine.inject_fault("ghost_flush", fixture_id=fixture.fixture_id, duration_minutes=15, severity="high")
    result = engine.run_tick(persist=False)
    target = next(
        reading
        for reading in result.readings
        if reading.fixture_id == fixture.fixture_id and reading.sensor_type == "flush_counter"
    )
    assert target.value >= 1


def test_sensor_dropout_marks_reading_stale(tmp_path):
    engine = SimulationEngine(
        preset_name="airport",
        database_path=tmp_path / "test.db",
        seed=3,
    )
    sensor = engine.topology.sensors[0]
    engine.inject_fault("sensor_dropout", sensor_id=sensor.sensor_id, duration_minutes=15, severity="high")
    result = engine.run_tick(persist=False)
    target = next(reading for reading in result.readings if reading.sensor_id == sensor.sensor_id)
    assert target.quality_flag == "stale"
    assert target.diagnostic_status == "offline"


def test_occupancy_spike_raises_zone_occupancy(tmp_path):
    engine = SimulationEngine(
        preset_name="airport",
        database_path=tmp_path / "test.db",
        start_time=datetime(2026, 1, 7, 12, 0, tzinfo=timezone.utc),
        seed=13,
    )
    zone = engine.topology.zones[0]
    baseline = engine.run_tick(persist=False).occupancy_by_zone[zone.zone_id]
    engine = SimulationEngine(
        preset_name="airport",
        database_path=tmp_path / "test2.db",
        start_time=datetime(2026, 1, 7, 12, 0, tzinfo=timezone.utc),
        seed=13,
    )
    engine.inject_fault("occupancy_spike", zone_id=zone.zone_id, duration_minutes=30, severity="medium")
    spiked = engine.run_tick(persist=False).occupancy_by_zone[zone.zone_id]
    assert spiked > baseline


def test_abnormal_flow_increases_flow(tmp_path):
    baseline_engine = SimulationEngine(
        preset_name="hospital",
        database_path=tmp_path / "baseline.db",
        start_time=datetime(2026, 1, 7, 10, 0, tzinfo=timezone.utc),
        seed=17,
    )
    fixture = baseline_engine.topology.fixtures[0]
    baseline_result = baseline_engine.run_tick(persist=False)
    baseline_flow = next(
        reading.value
        for reading in baseline_result.readings
        if reading.fixture_id == fixture.fixture_id and reading.sensor_type == "flow_meter"
    )

    fault_engine = SimulationEngine(
        preset_name="hospital",
        database_path=tmp_path / "fault.db",
        start_time=datetime(2026, 1, 7, 10, 0, tzinfo=timezone.utc),
        seed=17,
    )
    fault_engine.inject_fault("abnormal_flow", fixture_id=fixture.fixture_id, duration_minutes=30, severity="high")
    fault_result = fault_engine.run_tick(persist=False)
    fault_flow = next(
        reading.value
        for reading in fault_result.readings
        if reading.fixture_id == fixture.fixture_id and reading.sensor_type == "flow_meter"
    )
    assert fault_flow > baseline_flow
