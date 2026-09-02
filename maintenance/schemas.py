from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class MaintenanceRiskLevel(str, Enum):
    """
    Operational maintenance risk classification.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MaintenanceRiskInput(BaseModel):
    """
    Operational signals used to calculate maintenance risk.

    All values are normalized or bounded before entering
    the risk calculation.
    """

    fixture_id: str

    anomaly_count: int = Field(
        default=0,
        ge=0,
    )

    recent_anomaly_count: int = Field(
        default=0,
        ge=0,
    )

    high_severity_anomaly_count: int = Field(
        default=0,
        ge=0,
    )

    critical_anomaly_count: int = Field(
        default=0,
        ge=0,
    )

    sensor_health: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
    )

    abnormal_flow_events: int = Field(
        default=0,
        ge=0,
    )

    persistent_anomaly_minutes: float = Field(
        default=0.0,
        ge=0.0,
    )

    days_since_last_maintenance: float = Field(
        default=0.0,
        ge=0.0,
    )


class MaintenanceRiskResult(BaseModel):
    """
    Explainable maintenance-risk assessment.
    """

    fixture_id: str

    risk_score: float = Field(
        ge=0.0,
        le=100.0,
    )

    risk_level: MaintenanceRiskLevel

    contributing_factors: dict[str, float]

    recommended_action: str

    explanation: str