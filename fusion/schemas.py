from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class FusionDecision(str, Enum):
    """
    Final operational decision produced by the fusion engine.
    """

    NORMAL = "normal"
    RULE_ANOMALY = "rule_anomaly"
    ML_ANOMALY = "ml_anomaly"
    HIGH_CONFIDENCE_ANOMALY = "high_confidence_anomaly"
    SENSOR_ISSUE = "sensor_issue"


class FusionResult(BaseModel):
    """
    Combined result from deterministic rules and ML detection.
    """

    decision: FusionDecision

    rule_detected: bool

    ml_detected: bool

    rule_confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    ml_confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    combined_confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    reason: str

    rule_anomaly_type: str | None = None

    ml_model: str | None = None