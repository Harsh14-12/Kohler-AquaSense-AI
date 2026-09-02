from datetime import datetime, timedelta, timezone

from detection.explainer import (
    explain_anomaly,
    explain_with_evidence,
)
from detection.rule_engine import RuleConfig, RuleEngine
from detection.schemas import (
    AnomalySeverity,
    AnomalyStatus,
    AnomalyType,
)
from features.schemas import FeatureVector


def make_features(
    timestamp=None,
    flow=0.0,
    occupancy=0.0,
    average_flow=0.0,
    flow_variance=0.0,
    baseline_flow=0.0,
    baseline_sigma=0.0,
    baseline_deviation=0.0,
    flush_rate=0.0,
    idle_minutes=0.0,
    diagnostic_health=1.0,
    gap_minutes=0.0,
    occupancy_average=0.0,
):
    """Create a FeatureVector for rule-engine testing."""

    if timestamp is None:
        timestamp = datetime(
            2026,
            1,
            1,
            10,
            0,
            tzinfo=timezone.utc,
        )

    return FeatureVector(
        timestamp=timestamp,
        facility_id="facility-001",
        zone_id="zone-001",
        fixture_id="fixture-001",
        sensor_id="sensor-001",
        current_flow_rate=flow,
        average_flow_rate=average_flow,
        flow_variance=flow_variance,
        flow_change=0.0,
        occupancy=occupancy,
        occupancy_average=occupancy_average,
        flush_rate=flush_rate,
        flush_count=0.0,
        usage_per_occupant=0.0,
        idle_flow_minutes=idle_minutes,
        time_since_last_flush=0.0,
        time_since_last_usage=0.0,
        baseline_flow=baseline_flow,
        baseline_deviation=baseline_deviation,
        baseline_deviation_sigma=baseline_sigma,
        diagnostic_health=diagnostic_health,
        reading_gap_minutes=gap_minutes,
    )


# ============================================================
# ORIGINAL PHASE 2B-1 TESTS
# ============================================================


def test_engine_has_no_anomaly_for_normal_features():
    engine = RuleEngine()

    features = make_features(
        flow=0.05,
        occupancy=3.0,
        average_flow=0.05,
        baseline_flow=0.05,
        baseline_sigma=0.0,
        flush_rate=0.0,
        diagnostic_health=1.0,
        gap_minutes=5.0,
        occupancy_average=3.0,
    )

    events = engine.evaluate(features)

    assert events == []


def test_continuous_leak_requires_persistence():
    config = RuleConfig(
        leak_flow_threshold=0.50,
        leak_occupancy_threshold=0.10,
        leak_duration_minutes=10.0,
    )

    engine = RuleEngine(config)

    start = datetime(
        2026,
        1,
        1,
        10,
        0,
        tzinfo=timezone.utc,
    )

    first = make_features(
        timestamp=start,
        flow=2.0,
        occupancy=0.0,
    )

    second = make_features(
        timestamp=start + timedelta(minutes=5),
        flow=2.0,
        occupancy=0.0,
        idle_minutes=5.0,
    )

    third = make_features(
        timestamp=start + timedelta(minutes=10),
        flow=2.0,
        occupancy=0.0,
        idle_minutes=5.0,
    )

    assert engine.evaluate_leak(first) is None
    assert engine.evaluate_leak(second) is None

    event = engine.evaluate_leak(third)

    assert event is not None
    assert event.anomaly_type == AnomalyType.CONTINUOUS_LEAK
    assert event.status == AnomalyStatus.OPEN
    assert event.observed_value == 2.0
    assert event.expected_value == 0.0
    assert event.confidence >= 0.70


def test_continuous_leak_resets_when_condition_stops():
    config = RuleConfig(
        leak_flow_threshold=0.50,
        leak_occupancy_threshold=0.10,
        leak_duration_minutes=10.0,
    )

    engine = RuleEngine(config)

    start = datetime(
        2026,
        1,
        1,
        10,
        0,
        tzinfo=timezone.utc,
    )

    first = make_features(
        timestamp=start,
        flow=2.0,
        occupancy=0.0,
    )

    normal = make_features(
        timestamp=start + timedelta(minutes=5),
        flow=0.1,
        occupancy=2.0,
    )

    after_reset = make_features(
        timestamp=start + timedelta(minutes=15),
        flow=2.0,
        occupancy=0.0,
    )

    assert engine.evaluate_leak(first) is None
    assert engine.evaluate_leak(normal) is None
    assert engine.evaluate_leak(after_reset) is None


def test_abnormal_flow_rule():
    engine = RuleEngine()

    features = make_features(
        flow=2.0,
        baseline_flow=0.5,
        baseline_deviation=1.5,
        baseline_sigma=4.0,
    )

    event = engine.evaluate_abnormal_flow(features)

    assert event is not None
    assert event.anomaly_type == AnomalyType.ABNORMAL_FLOW
    assert event.observed_value == 2.0
    assert event.expected_value == 0.5
    assert event.confidence >= 0.70


def test_abnormal_flow_does_not_trigger_without_baseline():
    engine = RuleEngine()

    features = make_features(
        flow=2.0,
        baseline_flow=0.0,
        baseline_sigma=10.0,
    )

    assert engine.evaluate_abnormal_flow(features) is None


def test_ghost_flush_rule():
    engine = RuleEngine()

    features = make_features(
        occupancy=0.0,
        flush_rate=4.0,
    )

    event = engine.evaluate_ghost_flush(features)

    assert event is not None
    assert event.anomaly_type == AnomalyType.GHOST_FLUSH
    assert event.observed_value == 4.0
    assert event.expected_value == 0.0


def test_ghost_flush_not_triggered_when_occupied():
    engine = RuleEngine()

    features = make_features(
        occupancy=5.0,
        flush_rate=4.0,
    )

    assert engine.evaluate_ghost_flush(features) is None


def test_sensor_dropout_from_poor_health():
    engine = RuleEngine()

    features = make_features(
        diagnostic_health=0.0,
        gap_minutes=2.0,
    )

    event = engine.evaluate_sensor_dropout(features)

    assert event is not None
    assert event.anomaly_type == AnomalyType.SENSOR_DROPOUT
    assert event.confidence >= 0.85


def test_sensor_dropout_from_large_gap():
    engine = RuleEngine()

    features = make_features(
        diagnostic_health=1.0,
        gap_minutes=15.0,
    )

    event = engine.evaluate_sensor_dropout(features)

    assert event is not None
    assert event.anomaly_type == AnomalyType.SENSOR_DROPOUT
    assert event.confidence >= 0.85


def test_sensor_dropout_not_triggered_when_healthy():
    engine = RuleEngine()

    features = make_features(
        diagnostic_health=1.0,
        gap_minutes=5.0,
    )

    assert engine.evaluate_sensor_dropout(features) is None


def test_occupancy_spike():
    engine = RuleEngine()

    features = make_features(
        occupancy=20.0,
        occupancy_average=5.0,
    )

    event = engine.evaluate_occupancy_spike(features)

    assert event is not None
    assert event.anomaly_type == AnomalyType.OCCUPANCY_SPIKE
    assert event.observed_value == 20.0
    assert event.expected_value == 5.0


def test_occupancy_spike_not_triggered_for_normal_value():
    engine = RuleEngine()

    features = make_features(
        occupancy=6.0,
        occupancy_average=5.0,
    )

    assert engine.evaluate_occupancy_spike(features) is None


def test_event_severity_and_confidence_are_bounded():
    engine = RuleEngine()

    start = datetime(
        2026,
        1,
        1,
        10,
        0,
        tzinfo=timezone.utc,
    )

    first = make_features(
        timestamp=start,
        flow=5.0,
        occupancy=0.0,
    )

    second = make_features(
        timestamp=start + timedelta(minutes=10),
        flow=5.0,
        occupancy=0.0,
    )

    engine.evaluate_leak(first)

    event = engine.evaluate_leak(second)

    assert event is not None
    assert 0.0 <= event.confidence <= 1.0

    assert event.severity in {
        AnomalySeverity.LOW,
        AnomalySeverity.MEDIUM,
        AnomalySeverity.HIGH,
        AnomalySeverity.CRITICAL,
    }


def test_explanation_contains_rule_and_evidence():
    engine = RuleEngine()

    start = datetime(
        2026,
        1,
        1,
        10,
        0,
        tzinfo=timezone.utc,
    )

    first = make_features(
        timestamp=start,
        flow=2.0,
        occupancy=0.0,
    )

    second = make_features(
        timestamp=start + timedelta(minutes=10),
        flow=2.0,
        occupancy=0.0,
    )

    engine.evaluate_leak(first)

    event = engine.evaluate_leak(second)

    assert event is not None

    explanation = explain_anomaly(event)
    evidence = explain_with_evidence(event)

    assert explanation
    assert "Continuous leak suspected" in explanation
    assert "continuous_flow_while_unoccupied" in evidence
    assert "flow_rate_l_per_min" in evidence


def test_evaluate_runs_all_rules():
    engine = RuleEngine()

    features = make_features(
        flow=2.0,
        occupancy=0.0,
        baseline_flow=0.1,
        baseline_deviation=1.9,
        baseline_sigma=5.0,
        flush_rate=4.0,
        diagnostic_health=0.0,
        gap_minutes=15.0,
        occupancy_average=5.0,
    )

    events = engine.evaluate(features)

    anomaly_types = {
        event.anomaly_type
        for event in events
    }

    assert AnomalyType.ABNORMAL_FLOW in anomaly_types
    assert AnomalyType.GHOST_FLUSH in anomaly_types
    assert AnomalyType.SENSOR_DROPOUT in anomaly_types


# ============================================================
# PHASE 2B-2: ANOMALY LIFECYCLE TESTS
# ============================================================


def test_same_anomaly_is_deduplicated():
    """
    Repeated detection of the same anomaly should keep
    the same event ID.
    """

    engine = RuleEngine()

    start = datetime(
        2026,
        1,
        1,
        10,
        0,
        tzinfo=timezone.utc,
    )

    first = make_features(
        timestamp=start,
        flow=2.0,
        occupancy=0.0,
        idle_minutes=10.0,
    )

    second = make_features(
        timestamp=start + timedelta(minutes=10),
        flow=2.0,
        occupancy=0.0,
        idle_minutes=15.0,
    )

    # First evaluation starts persistence.
    first_events = engine.evaluate(first)

    # Second evaluation reaches 10-minute persistence.
    second_events = engine.evaluate(second)

    assert first_events == []
    assert len(second_events) >= 1

    leak_events = [
        event
        for event in second_events
        if event.anomaly_type
        == AnomalyType.CONTINUOUS_LEAK
    ]

    assert len(leak_events) == 1
    assert leak_events[0].status == AnomalyStatus.OPEN

    first_event_id = leak_events[0].event_id

    # Same anomaly continues.
    third = make_features(
        timestamp=start + timedelta(minutes=15),
        flow=2.0,
        occupancy=0.0,
        idle_minutes=20.0,
    )

    third_events = engine.evaluate(third)

    leak_events_again = [
        event
        for event in third_events
        if event.anomaly_type
        == AnomalyType.CONTINUOUS_LEAK
    ]

    assert len(leak_events_again) == 1

    assert (
        leak_events_again[0].event_id
        == first_event_id
    )

    assert (
        leak_events_again[0].status
        == AnomalyStatus.OPEN
    )


def test_different_anomaly_types_are_separate():
    """
    Different anomaly types must create separate events.
    """

    engine = RuleEngine()

    start = datetime(
        2026,
        1,
        1,
        10,
        0,
        tzinfo=timezone.utc,
    )

    features = make_features(
        timestamp=start,
        flow=2.0,
        occupancy=0.0,
        baseline_flow=0.1,
        baseline_deviation=1.9,
        baseline_sigma=5.0,
        flush_rate=4.0,
        diagnostic_health=1.0,
        gap_minutes=0.0,
    )

    events = engine.evaluate(features)

    anomaly_types = {
        event.anomaly_type
        for event in events
    }

    assert (
        AnomalyType.ABNORMAL_FLOW
        in anomaly_types
    )

    assert (
        AnomalyType.GHOST_FLUSH
        in anomaly_types
    )

    assert len(events) >= 2

    event_ids = {
        event.event_id
        for event in events
    }

    assert len(event_ids) == len(events)


def test_anomaly_resolves_when_condition_disappears():
    """
    An active anomaly should become RESOLVED when
    the condition disappears.
    """

    config = RuleConfig(
        leak_flow_threshold=0.50,
        leak_occupancy_threshold=0.10,
        leak_duration_minutes=5.0,
    )

    engine = RuleEngine(config)

    start = datetime(
        2026,
        1,
        1,
        10,
        0,
        tzinfo=timezone.utc,
    )

    first = make_features(
        timestamp=start,
        flow=2.0,
        occupancy=0.0,
    )

    second = make_features(
        timestamp=start + timedelta(minutes=5),
        flow=2.0,
        occupancy=0.0,
        idle_minutes=5.0,
    )

    engine.evaluate(first)

    events = engine.evaluate(second)

    leak_events = [
        event
        for event in events
        if event.anomaly_type
        == AnomalyType.CONTINUOUS_LEAK
    ]

    assert len(leak_events) == 1

    assert (
        leak_events[0].status
        == AnomalyStatus.OPEN
    )

    leak_event_id = leak_events[0].event_id

    # Leak disappears.
    healthy = make_features(
        timestamp=start + timedelta(minutes=10),
        flow=0.1,
        occupancy=2.0,
    )

    engine.evaluate(healthy)

    history = engine.get_event_history()

    resolved_events = [
        event
        for event in history
        if event.event_id == leak_event_id
    ]

    assert len(resolved_events) >= 1

    assert any(
        event.status
        == AnomalyStatus.RESOLVED
        for event in resolved_events
    )

    # It should no longer be active.
    active_events = engine.get_active_anomalies()

    assert all(
        event.event_id != leak_event_id
        for event in active_events
    )


def test_resolved_anomaly_can_occur_again():
    """
    A new anomaly after resolution should start
    a new lifecycle.
    """

    config = RuleConfig(
        leak_flow_threshold=0.50,
        leak_occupancy_threshold=0.10,
        leak_duration_minutes=5.0,
    )

    engine = RuleEngine(config)

    start = datetime(
        2026,
        1,
        1,
        10,
        0,
        tzinfo=timezone.utc,
    )

    # ========================================================
    # FIRST LEAK
    # ========================================================

    first = make_features(
        timestamp=start,
        flow=2.0,
        occupancy=0.0,
    )

    second = make_features(
        timestamp=start + timedelta(minutes=5),
        flow=2.0,
        occupancy=0.0,
        idle_minutes=5.0,
    )

    engine.evaluate(first)

    first_events = engine.evaluate(second)

    first_leaks = [
        event
        for event in first_events
        if event.anomaly_type
        == AnomalyType.CONTINUOUS_LEAK
    ]

    assert len(first_leaks) == 1

    first_event_id = first_leaks[0].event_id

    # ========================================================
    # HEALTHY PERIOD
    # ========================================================

    healthy = make_features(
        timestamp=start + timedelta(minutes=10),
        flow=0.1,
        occupancy=2.0,
    )

    engine.evaluate(healthy)

    history_after_resolution = (
        engine.get_event_history()
    )

    assert any(
        event.event_id == first_event_id
        and event.status
        == AnomalyStatus.RESOLVED
        for event in history_after_resolution
    )

    # ========================================================
    # SECOND LEAK
    # ========================================================

    third = make_features(
        timestamp=start + timedelta(minutes=15),
        flow=2.0,
        occupancy=0.0,
    )

    fourth = make_features(
        timestamp=start + timedelta(minutes=20),
        flow=2.0,
        occupancy=0.0,
        idle_minutes=5.0,
    )

    engine.evaluate(third)

    second_events = engine.evaluate(fourth)

    second_leaks = [
        event
        for event in second_events
        if event.anomaly_type
        == AnomalyType.CONTINUOUS_LEAK
    ]

    assert len(second_leaks) == 1

    second_event_id = second_leaks[0].event_id

    # A new occurrence should get a new lifecycle ID.
    assert second_event_id != first_event_id

    assert (
        second_leaks[0].status
        == AnomalyStatus.OPEN
    )