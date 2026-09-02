from datetime import datetime, timedelta, timezone

from features.feature_engine import FeatureEngine
from features.schemas import FeatureVector
from schemas.telemetry import (
    DiagnosticStatus,
    QualityFlag,
    SensorReading,
    SensorType,
    Unit,
)


def make_reading(
    sensor_id: str,
    sensor_type: SensorType,
    value: float,
    timestamp: datetime,
) -> SensorReading:
    """Create a valid Phase 1 SensorReading for testing."""

    unit_map = {
        SensorType.FLOW_METER: Unit.L_PER_MIN,
        SensorType.FLUSH_COUNTER: Unit.COUNT,
        SensorType.OCCUPANCY_PIR: Unit.PERSONS,
        SensorType.DIAGNOSTIC: Unit.STATUS_CODE,
    }

    return SensorReading(
        sensor_id=sensor_id,
        fixture_id="fixture-001",
        zone_id="zone-001",
        facility_id="facility-001",
        timestamp=timestamp,
        sensor_type=sensor_type,
        value=value,
        unit=unit_map[sensor_type],
        diagnostic_status=DiagnosticStatus.OK,
        quality_flag=QualityFlag.VALID,
    )


def test_feature_vector_validation():
    """FeatureVector should accept valid minimum data."""

    timestamp = datetime.now(timezone.utc)

    vector = FeatureVector(
        timestamp=timestamp,
        facility_id="facility-001",
        zone_id="zone-001",
        fixture_id="fixture-001",
        sensor_id="sensor-001",
    )

    assert vector.current_flow_rate == 0.0
    assert vector.occupancy == 0.0
    assert vector.diagnostic_health == 1.0


def test_current_flow_and_change():
    """Flow features should capture current value and change."""

    engine = FeatureEngine()

    timestamp = datetime(
        2026,
        1,
        1,
        10,
        0,
        tzinfo=timezone.utc,
    )

    first = make_reading(
        "flow-001",
        SensorType.FLOW_METER,
        1.0,
        timestamp,
    )

    second = make_reading(
        "flow-001",
        SensorType.FLOW_METER,
        2.5,
        timestamp + timedelta(minutes=5),
    )

    engine.update(first)
    features = engine.update(second)

    assert features.current_flow_rate == 2.5
    assert features.flow_change == 1.5


def test_rolling_average_and_variance():
    """Rolling mean and variance should be calculated correctly."""

    engine = FeatureEngine(window_size=3)

    timestamp = datetime(
        2026,
        1,
        1,
        10,
        0,
        tzinfo=timezone.utc,
    )

    values = [1.0, 2.0, 3.0]

    features = None

    for index, value in enumerate(values):
        features = engine.update(
            make_reading(
                "flow-001",
                SensorType.FLOW_METER,
                value,
                timestamp + timedelta(minutes=5 * index),
            )
        )

    assert features is not None
    assert features.average_flow_rate == 2.0

    assert round(
        features.flow_variance,
        6,
    ) == round(
        2 / 3,
        6,
    )


def test_occupancy_feature():
    """Occupancy should be extracted from the PIR sensor."""

    engine = FeatureEngine()

    timestamp = datetime(
        2026,
        1,
        1,
        10,
        0,
        tzinfo=timezone.utc,
    )

    occupancy = make_reading(
        "occupancy-001",
        SensorType.OCCUPANCY_PIR,
        5,
        timestamp,
    )

    features = engine.update(occupancy)

    assert features.occupancy == 5.0
    assert features.occupancy_average == 5.0


def test_cumulative_flush_counter():
    """Flush counter is cumulative, so increments represent usage."""

    engine = FeatureEngine()

    timestamp = datetime(
        2026,
        1,
        1,
        10,
        0,
        tzinfo=timezone.utc,
    )

    readings = [
        make_reading(
            "flush-001",
            SensorType.FLUSH_COUNTER,
            10,
            timestamp,
        ),
        make_reading(
            "flush-001",
            SensorType.FLUSH_COUNTER,
            11,
            timestamp + timedelta(minutes=5),
        ),
        make_reading(
            "flush-001",
            SensorType.FLUSH_COUNTER,
            13,
            timestamp + timedelta(minutes=10),
        ),
    ]

    features = None

    for reading in readings:
        features = engine.update(reading)

    assert features is not None
    assert features.flush_count == 13.0
    assert features.flush_rate == 3.0


def test_zero_occupancy_does_not_divide_by_zero():
    """Usage per occupant should remain safe when occupancy is zero."""

    engine = FeatureEngine()

    timestamp = datetime(
        2026,
        1,
        1,
        10,
        0,
        tzinfo=timezone.utc,
    )

    occupancy = make_reading(
        "occupancy-001",
        SensorType.OCCUPANCY_PIR,
        0,
        timestamp,
    )

    flush = make_reading(
        "flush-001",
        SensorType.FLUSH_COUNTER,
        5,
        timestamp,
    )

    engine.update(occupancy)
    features = engine.update(flush)

    assert features.usage_per_occupant == 0.0


def test_reading_gap():
    """Reading gaps should be measured in minutes."""

    engine = FeatureEngine()

    timestamp = datetime(
        2026,
        1,
        1,
        10,
        0,
        tzinfo=timezone.utc,
    )

    first = make_reading(
        "flow-001",
        SensorType.FLOW_METER,
        1.0,
        timestamp,
    )

    second = make_reading(
        "flow-001",
        SensorType.FLOW_METER,
        1.2,
        timestamp + timedelta(minutes=15),
    )

    engine.update(first)
    features = engine.update(second)

    assert features.reading_gap_minutes == 15.0


def test_diagnostic_health():
    """Offline diagnostics should produce zero health."""

    engine = FeatureEngine()

    timestamp = datetime(
        2026,
        1,
        1,
        10,
        0,
        tzinfo=timezone.utc,
    )

    diagnostic = make_reading(
        "diagnostic-001",
        SensorType.DIAGNOSTIC,
        3,
        timestamp,
    )

    diagnostic = diagnostic.copy(
        update={
            "diagnostic_status": DiagnosticStatus.OFFLINE
        }
    )

    features = engine.update(diagnostic)

    assert features.diagnostic_health == 0.0


def test_baseline_uses_previous_observations_only():
    """Baseline must not use the current/future observation."""

    engine = FeatureEngine(
        minimum_baseline_history=2,
        minimum_dispersion=0.05,
    )

    timestamp = datetime(
        2026,
        1,
        1,
        10,
        0,
        tzinfo=timezone.utc,
    )

    readings = [
        make_reading(
            "flow-001",
            SensorType.FLOW_METER,
            1.0,
            timestamp,
        ),
        make_reading(
            "flow-001",
            SensorType.FLOW_METER,
            1.1,
            timestamp + timedelta(minutes=5),
        ),
        make_reading(
            "flow-001",
            SensorType.FLOW_METER,
            3.0,
            timestamp + timedelta(minutes=10),
        ),
    ]

    engine.update(readings[0])
    engine.update(readings[1])
    features = engine.update(readings[2])

    assert features.baseline_flow == 1.05
    assert features.baseline_deviation > 0
    assert features.baseline_deviation_sigma > 0


def test_processing_is_deterministic():
    """Processing the same telemetry twice should give the same result."""

    timestamp = datetime(
        2026,
        1,
        1,
        10,
        0,
        tzinfo=timezone.utc,
    )

    readings = [
        make_reading(
            "flow-001",
            SensorType.FLOW_METER,
            1.0,
            timestamp,
        ),
        make_reading(
            "flow-001",
            SensorType.FLOW_METER,
            1.5,
            timestamp + timedelta(minutes=5),
        ),
    ]

    first = FeatureEngine().process(readings)
    second = FeatureEngine().process(readings)

    assert first == second