from datetime import datetime, timedelta, timezone

import pytest

from features.schemas import FeatureVector
from ml.anomaly_detector import IsolationForestDetector


def make_feature(
    timestamp: datetime,
    flow: float = 0.2,
    occupancy: float = 1.0,
    baseline_flow: float = 0.2,
    baseline_deviation: float = 0.0,
    baseline_sigma: float = 1.0,
) -> FeatureVector:
    return FeatureVector(
        timestamp=timestamp,
        facility_id="facility-001",
        zone_id="zone-001",
        fixture_id="fixture-001",
        sensor_id="sensor-001",
        current_flow_rate=flow,
        average_flow_rate=flow,
        flow_variance=0.01,
        flow_change=0.0,
        occupancy=occupancy,
        occupancy_average=occupancy,
        flush_rate=0.0,
        flush_count=0,
        usage_per_occupant=flow / max(occupancy, 1.0),
        idle_flow_minutes=0.0,
        time_since_last_flush=10.0,
        time_since_last_usage=10.0,
        baseline_flow=baseline_flow,
        baseline_deviation=baseline_deviation,
        baseline_deviation_sigma=baseline_sigma,
        diagnostic_health=1.0,
        reading_gap_minutes=0.0,
    )


def normal_training_data() -> list[FeatureVector]:
    start = datetime(
        2026,
        1,
        1,
        8,
        0,
        tzinfo=timezone.utc,
    )

    features = []

    for index in range(30):
        flow = 0.18 + (index % 5) * 0.01
        occupancy = 1.0 + (index % 3) * 0.2

        features.append(
            make_feature(
                timestamp=start + timedelta(
                    minutes=index
                ),
                flow=flow,
                occupancy=occupancy,
                baseline_flow=0.2,
            )
        )

    return features


def test_detector_requires_training():

    detector = IsolationForestDetector()

    feature = make_feature(
        timestamp=datetime(
            2026,
            1,
            1,
            10,
            0,
            tzinfo=timezone.utc,
        )
    )

    with pytest.raises(RuntimeError):
        detector.predict(feature)


def test_detector_requires_enough_training_data():

    detector = IsolationForestDetector()

    features = normal_training_data()[:5]

    with pytest.raises(ValueError):
        detector.fit(features)


def test_detector_fits_successfully():

    detector = IsolationForestDetector()

    features = normal_training_data()

    result = detector.fit(features)

    assert result is detector
    assert detector.is_fitted is True


def test_detector_prediction_has_valid_schema():

    detector = IsolationForestDetector()

    features = normal_training_data()

    detector.fit(features)

    feature = features[-1]

    result = detector.predict(feature)

    assert isinstance(
        result.is_anomaly,
        bool,
    )

    assert 0.0 <= result.anomaly_score <= 1.0

    assert 0.0 <= result.confidence <= 1.0

    assert (
        result.model_name
        == "IsolationForest"
    )

    assert result.features_used

    assert result.explanation


def test_detector_is_deterministic():

    features = normal_training_data()

    detector_a = IsolationForestDetector(
        random_state=42
    )

    detector_b = IsolationForestDetector(
        random_state=42
    )

    detector_a.fit(features)
    detector_b.fit(features)

    feature = features[-1]

    result_a = detector_a.predict(feature)
    result_b = detector_b.predict(feature)

    assert (
        result_a.is_anomaly
        == result_b.is_anomaly
    )

    assert (
        result_a.anomaly_score
        == result_b.anomaly_score
    )


def test_extreme_pattern_can_be_detected():

    features = normal_training_data()

    detector = IsolationForestDetector(
        contamination=0.05,
        random_state=42,
    )

    detector.fit(features)

    unusual = make_feature(
        timestamp=datetime(
            2026,
            1,
            2,
            12,
            0,
            tzinfo=timezone.utc,
        ),
        flow=8.0,
        occupancy=0.0,
        baseline_flow=0.2,
        baseline_deviation=7.8,
        baseline_sigma=1.0,
    )

    result = detector.predict(unusual)

    assert result.is_anomaly is True
    assert result.anomaly_score > 0.5