from __future__ import annotations

from pydantic import BaseModel, Field


class SustainabilityConfig(BaseModel):
    """
    Configurable assumptions used for sustainability calculations.

    These are prototype assumptions and should not be presented
    as official KOHLER specifications.
    """

    water_tariff_per_litre: float = Field(
        default=0.05,
        ge=0.0,
    )

    co2e_kg_per_1000_litres: float = Field(
        default=0.5,
        ge=0.0,
    )

    default_undetected_minutes: float = Field(
        default=30.0,
        ge=0.0,
    )


class SustainabilityImpact(BaseModel):
    """
    Sustainability impact calculated for one anomaly.
    """

    event_id: str

    facility_id: str

    zone_id: str

    fixture_id: str

    anomaly_type: str

    excess_flow_litres_per_minute: float = Field(
        ge=0.0,
    )

    duration_minutes: float = Field(
        ge=0.0,
    )

    litres_wasted: float = Field(
        ge=0.0,
    )

    potential_litres_saved: float = Field(
        ge=0.0,
    )

    estimated_cost: float = Field(
        ge=0.0,
    )

    potential_cost_saving: float = Field(
        ge=0.0,
    )

    estimated_co2e_kg: float = Field(
        ge=0.0,
    )

    calculation_trace: dict[str, float | str] = Field(
        default_factory=dict,
    )


class SustainabilitySummary(BaseModel):
    """
    Aggregated sustainability impact.
    """

    facility_id: str

    total_litres_wasted: float = Field(
        ge=0.0,
    )

    total_potential_litres_saved: float = Field(
        ge=0.0,
    )

    total_estimated_cost: float = Field(
        ge=0.0,
    )

    total_potential_cost_saving: float = Field(
        ge=0.0,
    )

    total_estimated_co2e_kg: float = Field(
        ge=0.0,
    )

    anomaly_count: int = Field(
        ge=0,
    )