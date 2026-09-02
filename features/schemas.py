"""Feature schemas used by the AquaSense anomaly detection pipeline."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class FeatureVector(BaseModel):
    """Derived fixture-level features at a point in time."""

    timestamp: datetime

    facility_id: str = Field(..., min_length=3)
    zone_id: str = Field(..., min_length=3)
    fixture_id: str = Field(..., min_length=3)
    sensor_id: str = Field(..., min_length=3)

    # Flow
    current_flow_rate: float = Field(default=0.0, ge=0.0)
    average_flow_rate: float = Field(default=0.0, ge=0.0)
    flow_variance: float = Field(default=0.0, ge=0.0)
    flow_change: float = 0.0

    # Occupancy
    occupancy: float = Field(default=0.0, ge=0.0)
    occupancy_average: float = Field(default=0.0, ge=0.0)

    # Usage
    flush_rate: float = Field(default=0.0, ge=0.0)
    flush_count: float = Field(default=0.0, ge=0.0)
    usage_per_occupant: float = Field(default=0.0, ge=0.0)
    idle_flow_minutes: float = Field(default=0.0, ge=0.0)
    time_since_last_flush: float = Field(default=0.0, ge=0.0)
    time_since_last_usage: float = Field(default=0.0, ge=0.0)

    # Baseline
    baseline_flow: float = Field(default=0.0, ge=0.0)
    baseline_deviation: float = 0.0
    baseline_deviation_sigma: float = 0.0

    # Data quality
    diagnostic_health: float = Field(default=1.0, ge=0.0, le=1.0)
    reading_gap_minutes: float = Field(default=0.0, ge=0.0)