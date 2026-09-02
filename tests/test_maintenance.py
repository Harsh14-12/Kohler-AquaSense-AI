import pytest

from maintenance.risk_engine import MaintenanceRiskEngine
from maintenance.schemas import (
    MaintenanceRiskInput,
    MaintenanceRiskLevel,
)


def test_normal_fixture_has_low_risk():

    engine = MaintenanceRiskEngine()

    data = MaintenanceRiskInput(
        fixture_id="fixture-001",
    )

    result = engine.calculate(data)

    assert result.risk_score == 0.0

    assert (
        result.risk_level
        == MaintenanceRiskLevel.LOW
    )

    assert result.recommended_action

    assert result.explanation


def test_repeated_anomalies_increase_risk():

    engine = MaintenanceRiskEngine()

    data = MaintenanceRiskInput(
        fixture_id="fixture-001",
        anomaly_count=5,
        recent_anomaly_count=4,
    )

    result = engine.calculate(data)

    assert result.risk_score > 0.0

    assert (
        result.contributing_factors[
            "anomaly_frequency"
        ] == 10.0
    )

    assert (
        result.contributing_factors[
            "recent_recurrence"
        ] == 16.0
    )


def test_high_severity_events_increase_risk():

    engine = MaintenanceRiskEngine()

    data = MaintenanceRiskInput(
        fixture_id="fixture-001",
        high_severity_anomaly_count=2,
        critical_anomaly_count=1,
    )

    result = engine.calculate(data)

    assert (
        result.contributing_factors[
            "severity"
        ] == 15.0
    )


def test_unhealthy_sensor_increases_risk():

    engine = MaintenanceRiskEngine()

    data = MaintenanceRiskInput(
        fixture_id="fixture-001",
        sensor_health=0.0,
    )

    result = engine.calculate(data)

    assert (
        result.contributing_factors[
            "sensor_health"
        ] == 10.0
    )


def test_persistent_anomaly_increases_risk():

    engine = MaintenanceRiskEngine()

    data = MaintenanceRiskInput(
        fixture_id="fixture-001",
        persistent_anomaly_minutes=60.0,
    )

    result = engine.calculate(data)

    assert (
        result.contributing_factors[
            "persistence"
        ] == 15.0
    )


def test_old_maintenance_increases_risk():

    engine = MaintenanceRiskEngine()

    data = MaintenanceRiskInput(
        fixture_id="fixture-001",
        days_since_last_maintenance=180.0,
    )

    result = engine.calculate(data)

    assert (
        result.contributing_factors[
            "maintenance_age"
        ] == 10.0
    )


def test_risk_score_is_bounded():

    engine = MaintenanceRiskEngine()

    data = MaintenanceRiskInput(
        fixture_id="fixture-001",
        anomaly_count=1000,
        recent_anomaly_count=1000,
        high_severity_anomaly_count=1000,
        critical_anomaly_count=1000,
        sensor_health=0.0,
        abnormal_flow_events=1000,
        persistent_anomaly_minutes=10000,
        days_since_last_maintenance=10000,
    )

    result = engine.calculate(data)

    assert 0.0 <= result.risk_score <= 100.0

    assert (
        result.risk_level
        == MaintenanceRiskLevel.CRITICAL
    )


def test_medium_risk_classification():

    engine = MaintenanceRiskEngine()

    data = MaintenanceRiskInput(
        fixture_id="fixture-001",
        anomaly_count=8,
        recent_anomaly_count=4,
    )

    result = engine.calculate(data)

    assert (
        result.risk_level
        == MaintenanceRiskLevel.MEDIUM
    )


def test_high_risk_classification():

    engine = MaintenanceRiskEngine()

    data = MaintenanceRiskInput(
        fixture_id="fixture-001",
        anomaly_count=10,
        recent_anomaly_count=5,
        high_severity_anomaly_count=2,
        abnormal_flow_events=2,
        persistent_anomaly_minutes=24,
    )

    result = engine.calculate(data)

    assert (
        result.risk_level
        in {
            MaintenanceRiskLevel.HIGH,
            MaintenanceRiskLevel.CRITICAL,
        }
    )

def test_contributing_factors_are_explainable():

    engine = MaintenanceRiskEngine()

    data = MaintenanceRiskInput(
        fixture_id="fixture-001",
        anomaly_count=3,
        recent_anomaly_count=2,
        abnormal_flow_events=2,
    )

    result = engine.calculate(data)

    assert result.contributing_factors

    assert all(
        value >= 0.0
        for value
        in result.contributing_factors.values()
    )

    assert "Primary contributing factors" in (
        result.explanation
    )


def test_recommended_action_changes_with_risk():

    engine = MaintenanceRiskEngine()

    low = engine.calculate(
        MaintenanceRiskInput(
            fixture_id="fixture-low",
        )
    )

    critical = engine.calculate(
        MaintenanceRiskInput(
            fixture_id="fixture-critical",
            anomaly_count=100,
            recent_anomaly_count=100,
            critical_anomaly_count=10,
            sensor_health=0.0,
            persistent_anomaly_minutes=100,
        )
    )

    assert (
        low.recommended_action
        != critical.recommended_action
    )


def test_same_input_is_deterministic():

    engine = MaintenanceRiskEngine()

    data = MaintenanceRiskInput(
        fixture_id="fixture-001",
        anomaly_count=4,
        recent_anomaly_count=3,
        high_severity_anomaly_count=1,
        abnormal_flow_events=2,
        persistent_anomaly_minutes=15,
    )

    result_a = engine.calculate(data)
    result_b = engine.calculate(data)

    assert result_a == result_b