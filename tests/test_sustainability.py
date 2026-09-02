from datetime import datetime, timezone

import pytest

from detection.schemas import (
    AnomalyEvent,
    AnomalySeverity,
    AnomalyStatus,
    AnomalyType,
    ExplanationTrace,
)
from sustainability.impact_engine import (
    SustainabilityImpactEngine,
)
from sustainability.schemas import (
    SustainabilityConfig,
)


def make_event(
    event_id: str = "event-001",
    excess_flow: float = 2.0,
    duration_minutes: float = 10.0,
) -> AnomalyEvent:

    return AnomalyEvent(
        event_id=event_id,
        facility_id="facility-001",
        zone_id="zone-001",
        fixture_id="fixture-001",
        timestamp=datetime(
            2026,
            1,
            1,
            10,
            0,
            tzinfo=timezone.utc,
        ),
        anomaly_type=AnomalyType.CONTINUOUS_LEAK,
        severity=AnomalySeverity.HIGH,
        confidence=0.95,
        status=AnomalyStatus.OPEN,
        triggered_rules=[
            "continuous_leak"
        ],
        triggering_features=[
            "current_flow_rate",
            "occupancy",
        ],
        observed_value=2.2,
        expected_value=0.2,
        explanation=(
            "Continuous leak suspected."
        ),
        explanation_trace=ExplanationTrace(
            rule="continuous_leak",
            observations={
                "flow_rate_l_per_min": 2.2,
                "duration_minutes": duration_minutes,
            },
            expected={
                "flow_rate_l_per_min": 0.2,
            },
            thresholds={
                "leak_flow_threshold": 0.5,
                "leak_duration_minutes": duration_minutes,
            },
            feature_deltas={
                "flow_excess": excess_flow,
            },
        ),
    )


def test_default_config():

    config = SustainabilityConfig()

    assert config.water_tariff_per_litre >= 0.0
    assert config.co2e_kg_per_1000_litres >= 0.0
    assert config.default_undetected_minutes >= 0.0


def test_custom_config():

    config = SustainabilityConfig(
        water_tariff_per_litre=0.10,
        co2e_kg_per_1000_litres=0.8,
        default_undetected_minutes=45.0,
    )

    assert config.water_tariff_per_litre == 0.10
    assert config.co2e_kg_per_1000_litres == 0.8
    assert config.default_undetected_minutes == 45.0


def test_calculates_water_waste():

    engine = SustainabilityImpactEngine()

    event = make_event(
        excess_flow=2.0,
        duration_minutes=10.0,
    )

    impact = engine.calculate(event)

    assert impact.litres_wasted == pytest.approx(
        20.0
    )


def test_calculates_cost():

    config = SustainabilityConfig(
        water_tariff_per_litre=0.05
    )

    engine = SustainabilityImpactEngine(
        config=config
    )

    event = make_event(
        excess_flow=2.0,
        duration_minutes=10.0,
    )

    impact = engine.calculate(event)

    assert impact.estimated_cost == pytest.approx(
        1.0
    )

    assert (
        impact.potential_cost_saving
        == pytest.approx(1.0)
    )


def test_calculates_co2e():

    config = SustainabilityConfig(
        co2e_kg_per_1000_litres=0.5
    )

    engine = SustainabilityImpactEngine(
        config=config
    )

    event = make_event(
        excess_flow=2.0,
        duration_minutes=10.0,
    )

    impact = engine.calculate(event)

    assert impact.estimated_co2e_kg == pytest.approx(
        0.01
    )


def test_calculation_trace_is_explainable():

    engine = SustainabilityImpactEngine()

    event = make_event(
        excess_flow=2.0,
        duration_minutes=10.0,
    )

    impact = engine.calculate(event)

    assert (
        impact.calculation_trace["excess_flow"]
        == 2.0
    )

    assert (
        impact.calculation_trace[
            "duration_minutes"
        ]
        == 10.0
    )

    assert "formula" in impact.calculation_trace


def test_summary_aggregates_multiple_impacts():

    engine = SustainabilityImpactEngine()

    event_a = make_event(
        event_id="event-a",
        excess_flow=2.0,
        duration_minutes=10.0,
    )

    event_b = make_event(
        event_id="event-b",
        excess_flow=1.0,
        duration_minutes=20.0,
    )

    impact_a = engine.calculate(event_a)
    impact_b = engine.calculate(event_b)

    summary = engine.summarize(
        [impact_a, impact_b],
        facility_id="facility-001",
    )

    assert summary.anomaly_count == 2

    assert summary.total_litres_wasted == pytest.approx(
        40.0
    )

    assert (
        summary.total_potential_litres_saved
        == pytest.approx(40.0)
    )


def test_summary_cost_matches_impacts():

    engine = SustainabilityImpactEngine()

    event_a = make_event(
        event_id="event-a",
        excess_flow=2.0,
        duration_minutes=10.0,
    )

    event_b = make_event(
        event_id="event-b",
        excess_flow=1.0,
        duration_minutes=20.0,
    )

    impact_a = engine.calculate(event_a)
    impact_b = engine.calculate(event_b)

    summary = engine.summarize(
        [impact_a, impact_b],
        facility_id="facility-001",
    )

    expected_cost = (
        impact_a.estimated_cost
        + impact_b.estimated_cost
    )

    assert (
        summary.total_estimated_cost
        == pytest.approx(expected_cost)
    )


def test_zero_excess_flow_has_zero_waste():

    engine = SustainabilityImpactEngine()

    event = make_event(
        excess_flow=0.0,
        duration_minutes=10.0,
    )

    impact = engine.calculate(event)

    assert impact.litres_wasted == 0.0
    assert impact.potential_litres_saved == 0.0
    assert impact.estimated_cost == 0.0