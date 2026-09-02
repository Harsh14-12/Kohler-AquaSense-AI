from datetime import datetime, timezone

from detection.schemas import (
    AnomalyEvent,
    AnomalySeverity,
    AnomalyStatus,
    AnomalyType,
    ExplanationTrace,
)
from fusion.fusion_engine import FusionEngine
from fusion.schemas import FusionDecision
from ml.schemas import MLAnomalyResult


def make_rule_event(
    anomaly_type: AnomalyType = AnomalyType.CONTINUOUS_LEAK,
    confidence: float = 0.9,
) -> AnomalyEvent:

    return AnomalyEvent(
        event_id="event-001",
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
        anomaly_type=anomaly_type,
        severity=AnomalySeverity.HIGH,
        confidence=confidence,
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


def make_ml_result(
    is_anomaly: bool = True,
    confidence: float = 0.8,
) -> MLAnomalyResult:

    return MLAnomalyResult(
        is_anomaly=is_anomaly,
        anomaly_score=0.75 if is_anomaly else 0.1,
        confidence=confidence,
        model_name="IsolationForest",
        features_used=[
            "current_flow_rate",
            "occupancy",
        ],
        explanation=(
            "ML detected unusual behaviour."
        ),
    )


def test_normal_operation():

    engine = FusionEngine()

    result = engine.combine(
        rule_event=None,
        ml_result=make_ml_result(
            is_anomaly=False,
            confidence=0.9,
        ),
    )

    assert result.decision == FusionDecision.NORMAL
    assert result.rule_detected is False
    assert result.ml_detected is False


def test_rule_only_anomaly():

    engine = FusionEngine()

    event = make_rule_event()

    result = engine.combine(
        rule_event=event,
        ml_result=make_ml_result(
            is_anomaly=False
        ),
    )

    assert result.decision == FusionDecision.RULE_ANOMALY
    assert result.rule_detected is True
    assert result.ml_detected is False
    assert result.combined_confidence == event.confidence


def test_ml_only_anomaly():

    engine = FusionEngine()

    result = engine.combine(
        rule_event=None,
        ml_result=make_ml_result(
            is_anomaly=True,
            confidence=0.8,
        ),
    )

    assert result.decision == FusionDecision.ML_ANOMALY
    assert result.rule_detected is False
    assert result.ml_detected is True
    assert result.combined_confidence == 0.8


def test_both_detectors_produce_high_confidence_anomaly():

    engine = FusionEngine()

    event = make_rule_event(
        confidence=0.9
    )

    ml_result = make_ml_result(
        is_anomaly=True,
        confidence=0.8,
    )

    result = engine.combine(
        rule_event=event,
        ml_result=ml_result,
    )

    assert (
        result.decision
        == FusionDecision.HIGH_CONFIDENCE_ANOMALY
    )

    assert result.rule_detected is True
    assert result.ml_detected is True

    expected = (
        0.6 * 0.9
        + 0.4 * 0.8
    )

    assert result.combined_confidence == expected


def test_sensor_issue_takes_priority():

    engine = FusionEngine()

    event = make_rule_event(
        anomaly_type=AnomalyType.SENSOR_DROPOUT,
        confidence=0.95,
    )

    result = engine.combine(
        rule_event=event,
        ml_result=make_ml_result(
            is_anomaly=True,
            confidence=0.9,
        ),
    )

    assert (
        result.decision
        == FusionDecision.SENSOR_ISSUE
    )

    assert result.combined_confidence == 0.95


def test_fusion_is_deterministic():

    engine = FusionEngine()

    event = make_rule_event(
        confidence=0.85
    )

    ml_result = make_ml_result(
        is_anomaly=True,
        confidence=0.75,
    )

    result_a = engine.combine(
        rule_event=event,
        ml_result=ml_result,
    )

    result_b = engine.combine(
        rule_event=event,
        ml_result=ml_result,
    )

    assert result_a == result_b