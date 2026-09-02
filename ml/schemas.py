from __future__ import annotations

from pydantic import BaseModel, Field


class MLAnomalyResult(BaseModel):
    """
    Result produced by the statistical anomaly detector.
    """

    is_anomaly: bool

    anomaly_score: float

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    model_name: str

    features_used: list[str]

    explanation: str