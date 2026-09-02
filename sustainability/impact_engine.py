from __future__ import annotations

from typing import Iterable

from detection.schemas import AnomalyEvent

from .schemas import (
    SustainabilityConfig,
    SustainabilityImpact,
    SustainabilitySummary,
)


class SustainabilityImpactEngine:
    """
    Converts operational anomalies into measurable
    sustainability and financial impact.

    Core calculation:

        litres_wasted =
            excess_flow_litres_per_minute
            ×
            duration_minutes

    This engine is intentionally deterministic and explainable.
    """

    def __init__(
        self,
        config: SustainabilityConfig | None = None,
    ) -> None:
        self.config = (
            config
            if config is not None
            else SustainabilityConfig()
        )

    # ------------------------------------------------------------------
    # Flow extraction
    # ------------------------------------------------------------------

    def _extract_excess_flow(
        self,
        event: AnomalyEvent,
    ) -> float:
        """
        Extract the excess flow associated with an anomaly.

        Priority:

        1. feature_deltas["flow_excess"]
        2. observed_value - expected_value
        3. zero
        """

        trace = event.explanation_trace

        if "flow_excess" in trace.feature_deltas:
            value = float(
                trace.feature_deltas["flow_excess"]
            )

            return max(
                0.0,
                value,
            )

        if (
            event.observed_value is not None
            and event.expected_value is not None
        ):
            return max(
                0.0,
                float(event.observed_value)
                - float(event.expected_value),
            )

        return 0.0

    # ------------------------------------------------------------------
    # Duration extraction
    # ------------------------------------------------------------------

    def _extract_duration(
        self,
        event: AnomalyEvent,
    ) -> float:
        """
        Extract anomaly duration from the explanation trace.

        If the trace does not contain a duration, use the configured
        prototype default.
        """

        observations = (
            event.explanation_trace.observations
        )

        possible_keys = [
            "duration_minutes",
            "leak_duration_minutes",
            "duration",
        ]

        for key in possible_keys:
            if key in observations:
                return max(
                    0.0,
                    float(observations[key]),
                )

        thresholds = (
            event.explanation_trace.thresholds
        )

        if "leak_duration_minutes" in thresholds:
            return max(
                0.0,
                float(
                    thresholds[
                        "leak_duration_minutes"
                    ]
                ),
            )

        return self.config.default_undetected_minutes

    # ------------------------------------------------------------------
    # Single anomaly calculation
    # ------------------------------------------------------------------

    def calculate(
        self,
        event: AnomalyEvent,
    ) -> SustainabilityImpact:
        """
        Calculate sustainability impact for one anomaly.
        """

        excess_flow = self._extract_excess_flow(
            event
        )

        duration = self._extract_duration(
            event
        )

        litres_wasted = (
            excess_flow
            * duration
        )

        potential_litres_saved = litres_wasted

        estimated_cost = (
            litres_wasted
            * self.config.water_tariff_per_litre
        )

        potential_cost_saving = (
            potential_litres_saved
            * self.config.water_tariff_per_litre
        )

        estimated_co2e_kg = (
            litres_wasted
            / 1000.0
            * self.config.co2e_kg_per_1000_litres
        )

        calculation_trace = {
            "formula": (
                "excess_flow_litres_per_minute "
                "* duration_minutes"
            ),
            "excess_flow": excess_flow,
            "duration_minutes": duration,
            "water_tariff_per_litre": (
                self.config.water_tariff_per_litre
            ),
            "co2e_kg_per_1000_litres": (
                self.config.co2e_kg_per_1000_litres
            ),
        }

        return SustainabilityImpact(
            event_id=event.event_id,
            facility_id=event.facility_id,
            zone_id=event.zone_id,
            fixture_id=event.fixture_id,
            anomaly_type=event.anomaly_type.value,
            excess_flow_litres_per_minute=excess_flow,
            duration_minutes=duration,
            litres_wasted=litres_wasted,
            potential_litres_saved=potential_litres_saved,
            estimated_cost=estimated_cost,
            potential_cost_saving=potential_cost_saving,
            estimated_co2e_kg=estimated_co2e_kg,
            calculation_trace=calculation_trace,
        )

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------

    def summarize(
        self,
        impacts: Iterable[SustainabilityImpact],
        facility_id: str,
    ) -> SustainabilitySummary:
        """
        Aggregate sustainability impacts for one facility.
        """

        impact_list = list(impacts)

        return SustainabilitySummary(
            facility_id=facility_id,
            total_litres_wasted=sum(
                impact.litres_wasted
                for impact in impact_list
            ),
            total_potential_litres_saved=sum(
                impact.potential_litres_saved
                for impact in impact_list
            ),
            total_estimated_cost=sum(
                impact.estimated_cost
                for impact in impact_list
            ),
            total_potential_cost_saving=sum(
                impact.potential_cost_saving
                for impact in impact_list
            ),
            total_estimated_co2e_kg=sum(
                impact.estimated_co2e_kg
                for impact in impact_list
            ),
            anomaly_count=len(
                impact_list
            ),
        )