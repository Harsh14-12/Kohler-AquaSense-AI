from datetime import datetime, timedelta, timezone

import pytest

from detection.schemas import (
    AnomalyEvent,
    AnomalySeverity,
    AnomalyStatus,
    AnomalyType,
    ExplanationTrace,
)
from maintenance.risk_builder import (
    MaintenanceRiskBuilder,
)


def make_event(
    event_id: str,
    fixture_id: str,
    timestamp: datetime,
    anomaly_type: AnomalyType = AnomalyType.CONTINUOUS_LEAK,
    severity: AnomalySeverity = AnomalySeverity.HIGH,
) -> AnomalyEvent:

    return AnomalyEvent(
        event_id=event_id,
        facility_id="facility-001",
        zone_id="zone-001",
        fixture_id=fixture_id,
        timestamp=timestamp,
        anomaly_type=anomaly_type,
        severity=severity,
        confidence=0.9,
        status=AnomalyStatus.OPEN,
        triggered_rules=[
            anomaly_type.value
        ],
        triggering_features=[
            "current_flow_rate"
        ],
        observed_value=2.0,
        expected_value=0.2,
        explanation="Test anomaly.",
        explanation_trace=ExplanationTrace(
            rule=anomaly_type.value,
            observations={
                "flow_rate_l_per_min": 2.0
            },
            expected={
                "flow_rate_l_per_min": 0.2
            },
            thresholds={
                "threshold": 0.5
            },
            feature_deltas={
                "flow_excess": 1.8
            },
        ),
    )


def test_empty_history_produces_zero_counts():

    builder = MaintenanceRiskBuilder()

    result = builder.build(
        fixture_id="fixture-001",
        events=[],
        reference_time=datetime(
            2026,
            1,
            10,
            12,
            0,
            tzinfo=timezone.utc,
        ),
    )

    assert result.anomaly_count == 0
    assert result.recent_anomaly_count == 0
    assert result.high_severity_anomaly_count == 0
    assert result.critical_anomaly_count == 0
    assert result.abnormal_flow_events == 0
    assert result.persistent_anomaly_minutes == 0.0


def test_only_matching_fixture_events_are_used():

    builder = MaintenanceRiskBuilder()

    timestamp = datetime(
        2026,
        1,
        10,
        12,
        0,
        tzinfo=timezone.utc,
    )

    events = [
        make_event(
            "event-001",
            "fixture-001",
            timestamp,
        ),
        make_event(
            "event-002",
            "fixture-002",
            timestamp,
        ),
    ]

    result = builder.build(
        fixture_id="fixture-001",
        events=events,
        reference_time=timestamp,
    )

    assert result.anomaly_count == 1


def test_recent_anomalies_are_counted():

    builder = MaintenanceRiskBuilder(
        recent_window_days=7.0
    )

    reference = datetime(
        2026,
        1,
        10,
        12,
        0,
        tzinfo=timezone.utc,
    )

    events = [
        make_event(
            "event-old",
            "fixture-001",
            reference - timedelta(days=10),
        ),
        make_event(
            "event-recent",
            "fixture-001",
            reference - timedelta(days=2),
        ),
    ]

    result = builder.build(
        fixture_id="fixture-001",
        events=events,
        reference_time=reference,
    )

    assert result.anomaly_count == 2
    assert result.recent_anomaly_count == 1


def test_high_and_critical_severity_are_counted():

    builder = MaintenanceRiskBuilder()

    timestamp = datetime(
        2026,
        1,
        10,
        12,
        0,
        tzinfo=timezone.utc,
    )

    events = [
        make_event(
            "event-high",
            "fixture-001",
            timestamp,
            severity=AnomalySeverity.HIGH,
        ),
        make_event(
            "event-critical",
            "fixture-001",
            timestamp + timedelta(minutes=5),
            severity=AnomalySeverity.CRITICAL,
        ),
        make_event(
            "event-medium",
            "fixture-001",
            timestamp + timedelta(minutes=10),
            severity=AnomalySeverity.MEDIUM,
        ),
    ]

    result = builder.build(
        fixture_id="fixture-001",
        events=events,
        reference_time=timestamp,
    )

    assert result.high_severity_anomaly_count == 2
    assert result.critical_anomaly_count == 1


def test_abnormal_flow_events_are_counted():

    builder = MaintenanceRiskBuilder()

    timestamp = datetime(
        2026,
        1,
        10,
        12,
        0,
        tzinfo=timezone.utc,
    )

    events = [
        make_event(
            "event-1",
            "fixture-001",
            timestamp,
            anomaly_type=AnomalyType.ABNORMAL_FLOW,
        ),
        make_event(
            "event-2",
            "fixture-001",
            timestamp + timedelta(minutes=5),
            anomaly_type=AnomalyType.CONTINUOUS_LEAK,
        ),
        make_event(
            "event-3",
            "fixture-001",
            timestamp + timedelta(minutes=10),
            anomaly_type=AnomalyType.ABNORMAL_FLOW,
        ),
    ]

    result = builder.build(
        fixture_id="fixture-001",
        events=events,
        reference_time=timestamp,
    )

    assert result.abnormal_flow_events == 2


def test_persistence_is_calculated_from_event_intervals():

    builder = MaintenanceRiskBuilder()

    start = datetime(
        2026,
        1,
        10,
        12,
        0,
        tzinfo=timezone.utc,
    )

    events = [
        make_event(
            "event-1",
            "fixture-001",
            start,
        ),
        make_event(
            "event-2",
            "fixture-001",
            start + timedelta(minutes=10),
        ),
        make_event(
            "event-3",
            "fixture-001",
            start + timedelta(minutes=25),
        ),
    ]

    result = builder.build(
        fixture_id="fixture-001",
        events=events,
        reference_time=start,
    )

    assert result.persistent_anomaly_minutes == pytest.approx(
        25.0
    )


def test_sensor_health_is_passed_through():

    builder = MaintenanceRiskBuilder()

    result = builder.build(
        fixture_id="fixture-001",
        events=[],
        sensor_health=0.75,
    )

    assert result.sensor_health == 0.75


def test_maintenance_age_is_passed_through():

    builder = MaintenanceRiskBuilder()

    result = builder.build(
        fixture_id="fixture-001",
        events=[],
        days_since_last_maintenance=120.0,
    )

    assert (
        result.days_since_last_maintenance
        == 120.0
    )


def test_invalid_sensor_health_is_rejected():

    builder = MaintenanceRiskBuilder()

    with pytest.raises(ValueError):
        builder.build(
            fixture_id="fixture-001",
            events=[],
            sensor_health=1.5,
        )


def test_invalid_maintenance_age_is_rejected():

    builder = MaintenanceRiskBuilder()

    with pytest.raises(ValueError):
        builder.build(
            fixture_id="fixture-001",
            events=[],
            days_since_last_maintenance=-1.0,
        )


def test_builder_is_deterministic_with_reference_time():

    builder = MaintenanceRiskBuilder()

    reference = datetime(
        2026,
        1,
        10,
        12,
        0,
        tzinfo=timezone.utc,
    )

    events = [
        make_event(
            "event-1",
            "fixture-001",
            reference - timedelta(hours=1),
        ),
        make_event(
            "event-2",
            "fixture-001",
            reference,
        ),
    ]

    result_a = builder.build(
        fixture_id="fixture-001",
        events=events,
        reference_time=reference,
    )

    result_b = builder.build(
        fixture_id="fixture-001",
        events=events,
        reference_time=reference,
    )

    assert result_a == result_b