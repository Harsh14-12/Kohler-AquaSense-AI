"""Schemas for explainable AquaSense anomaly events."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class AnomalyType(str, Enum):
    CONTINUOUS_LEAK = "continuous_leak"
    ABNORMAL_FLOW = "abnormal_flow"
    GHOST_FLUSH = "ghost_flush"
    SENSOR_DROPOUT = "sensor_dropout"
    OCCUPANCY_SPIKE = "occupancy_spike"


class AnomalySeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnomalyStatus(str, Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class ExplanationTrace(BaseModel):
    """Structured evidence explaining why an anomaly was detected."""

    rule: str
    observations: dict[str, float | str | bool]
    expected: dict[str, float | str | bool]
    thresholds: dict[str, float | str | bool]
    feature_deltas: dict[str, float | str | bool]


class AnomalyEvent(BaseModel):
    """Explainable anomaly generated from a FeatureVector."""

    event_id: str

    facility_id: str
    zone_id: str
    fixture_id: str
    timestamp: datetime

    anomaly_type: AnomalyType
    severity: AnomalySeverity
    confidence: float = Field(..., ge=0.0, le=1.0)

    status: AnomalyStatus = AnomalyStatus.OPEN

    triggered_rules: list[str] = Field(default_factory=list)
    triggering_features: list[str] = Field(default_factory=list)

    observed_value: float | None = None
    expected_value: float | None = None

    explanation: str

    explanation_trace: ExplanationTrace