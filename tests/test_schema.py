from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from schemas.telemetry import SensorReading


def build_reading(**overrides):
    payload = {
        "sensor_id": "sensor-001",
        "fixture_id": "fixture-001",
        "zone_id": "zone-001",
        "facility_id": "facility-001",
        "timestamp": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "sensor_type": "flow_meter",
        "value": 1.5,
        "unit": "L_per_min",
        "diagnostic_status": "ok",
        "quality_flag": "valid",
        "metadata": {},
    }
    payload.update(overrides)
    return SensorReading(**payload)


def test_valid_sensor_reading():
    reading = build_reading()
    assert reading.sensor_type == "flow_meter"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("sensor_type", "bad_sensor"),
        ("unit", "psi"),
        ("diagnostic_status", "warning"),
        ("quality_flag", "broken"),
    ],
)
def test_invalid_enums(field, value):
    with pytest.raises(ValidationError):
        build_reading(**{field: value})


def test_incompatible_sensor_unit_rejected():
    with pytest.raises(ValidationError):
        build_reading(sensor_type="flush_counter", unit="L_per_min", value=1.0)
