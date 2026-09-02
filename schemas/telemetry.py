"""Telemetry schemas used by the simulator and persistence layer."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, root_validator, validator


class SensorType(str, Enum):
    FLOW_METER = "flow_meter"
    FLUSH_COUNTER = "flush_counter"
    OCCUPANCY_PIR = "occupancy_pir"
    DIAGNOSTIC = "diagnostic"


class Unit(str, Enum):
    L_PER_MIN = "L_per_min"
    COUNT = "count"
    PERSONS = "persons"
    STATUS_CODE = "status_code"


class DiagnosticStatus(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    BATTERY_LOW = "battery_low"


class QualityFlag(str, Enum):
    VALID = "valid"
    INTERPOLATED = "interpolated"
    STALE = "stale"
    OUT_OF_RANGE = "out_of_range"


SENSOR_UNIT_MAP = {
    SensorType.FLOW_METER: Unit.L_PER_MIN,
    SensorType.FLUSH_COUNTER: Unit.COUNT,
    SensorType.OCCUPANCY_PIR: Unit.PERSONS,
    SensorType.DIAGNOSTIC: Unit.STATUS_CODE,
}


class SensorReading(BaseModel):
    """Normalized telemetry reading used across the Phase 1 stack."""

    sensor_id: str = Field(..., min_length=3, max_length=128)
    fixture_id: str = Field(..., min_length=3, max_length=128)
    zone_id: str = Field(..., min_length=3, max_length=128)
    facility_id: str = Field(..., min_length=3, max_length=128)
    timestamp: datetime
    sensor_type: SensorType
    value: float
    unit: Unit
    diagnostic_status: DiagnosticStatus
    quality_flag: QualityFlag
    metadata: dict[str, Any] = Field(default_factory=dict)

    @validator("timestamp")
    def ensure_datetime(cls, value: datetime) -> datetime:
        if not isinstance(value, datetime):
            raise TypeError("timestamp must be a datetime instance")
        return value

    @validator("value")
    def ensure_finite_value(cls, value: float) -> float:
        if value != value:
            raise ValueError("value must not be NaN")
        return value

    @root_validator
    def validate_value_and_unit(cls, values: dict[str, Any]) -> dict[str, Any]:
        raw_sensor_type = values.get("sensor_type")
        raw_unit = values.get("unit")
        value = values.get("value")

        sensor_type = SensorType(raw_sensor_type) if raw_sensor_type is not None else None
        unit = Unit(raw_unit) if raw_unit is not None else None

        if sensor_type is not None and unit is not None:
            expected_unit = SENSOR_UNIT_MAP[sensor_type]
            if unit != expected_unit:
                raise ValueError(
                    f"{sensor_type.value} readings must use unit {expected_unit.value}"
                )

        if sensor_type in (
            SensorType.FLOW_METER,
            SensorType.FLUSH_COUNTER,
            SensorType.OCCUPANCY_PIR,
        ) and value is not None and value < 0:
            raise ValueError("value must be non-negative for physical telemetry")

        if sensor_type == SensorType.FLUSH_COUNTER and value is not None and value % 1:
            raise ValueError("flush_counter values must be whole numbers")

        if sensor_type == SensorType.DIAGNOSTIC and value is not None:
            allowed_codes = {0.0, 1.0, 2.0, 3.0}
            if value not in allowed_codes:
                raise ValueError("diagnostic values must be one of 0, 1, 2, 3")

        return values

    class Config:
        use_enum_values = True
