from __future__ import annotations

from datetime import datetime, timezone

from simulator.simulation_engine import SimulationEngine


def test_same_seed_produces_equivalent_output(tmp_path):
    engine_one = SimulationEngine(
        preset_name="airport",
        database_path=tmp_path / "one.db",
        start_time=datetime(2026, 1, 7, 8, 0, tzinfo=timezone.utc),
        seed=21,
    )
    engine_two = SimulationEngine(
        preset_name="airport",
        database_path=tmp_path / "two.db",
        start_time=datetime(2026, 1, 7, 8, 0, tzinfo=timezone.utc),
        seed=21,
    )

    result_one = engine_one.run_tick(persist=False)
    result_two = engine_two.run_tick(persist=False)

    snapshot_one = [
        (reading.sensor_id, reading.value, reading.diagnostic_status, reading.quality_flag)
        for reading in result_one.readings[:10]
    ]
    snapshot_two = [
        (reading.sensor_id, reading.value, reading.diagnostic_status, reading.quality_flag)
        for reading in result_two.readings[:10]
    ]
    assert result_one.occupancy_by_zone == result_two.occupancy_by_zone
    assert snapshot_one == snapshot_two
