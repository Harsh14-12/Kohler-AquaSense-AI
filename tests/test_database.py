from __future__ import annotations

from datetime import datetime, timezone

from database import TelemetryRepository, create_session_factory, init_db
from schemas.telemetry import SensorReading
from simulator.facility_topology import build_facility_topology


def test_database_insertion_and_queries(tmp_path):
    database_path = tmp_path / "telemetry.db"
    init_db(database_path)
    repository = TelemetryRepository(create_session_factory(database_path))
    topology = build_facility_topology("hospital")
    repository.register_topology(topology)

    sensor = topology.sensors[0]
    reading = SensorReading(
        sensor_id=sensor.sensor_id,
        fixture_id=sensor.fixture_id,
        zone_id=sensor.zone_id,
        facility_id=sensor.facility_id,
        timestamp=datetime(2026, 1, 7, 9, 0, tzinfo=timezone.utc),
        sensor_type=sensor.sensor_type,
        value=1.5 if sensor.sensor_type == "flow_meter" else 0.0,
        unit=sensor.unit,
        diagnostic_status="ok",
        quality_flag="valid",
        metadata={"source": "test"},
    )

    repository.save_sensor_reading(reading)
    recent = repository.get_recent_readings(limit=5)
    fixture_rows = repository.get_readings_for_fixture(sensor.fixture_id, limit=5)

    assert len(recent) == 1
    assert len(fixture_rows) == 1
    assert fixture_rows[0].sensor_id == sensor.sensor_id
