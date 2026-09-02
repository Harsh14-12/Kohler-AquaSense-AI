from datetime import datetime, timedelta, timezone

from app.pipeline import AquaSensePipeline
from schemas.telemetry import SensorReading


def make_reading(
    timestamp: datetime,
    value: float,
    occupancy: int = 0,
    flush_count: int = 0,
) -> SensorReading:
    return SensorReading(
        timestamp=timestamp,
        facility_id="facility_test",
        zone_id="zone_test",
        fixture_id="fixture_test",
        sensor_id="sensor_test",
        sensor_type="flow_meter",
        value=value,
        unit="L_per_min",
        occupancy=occupancy,
        flush_count=flush_count,
        diagnostic_status="ok",
        quality_flag="valid",
    )


def test_pipeline_detects_leak_and_creates_ticket():
    pipeline = AquaSensePipeline()

    start = datetime.now(timezone.utc)

    result = None

    # ---------------------------------------------------------
    # 1. Build 10 minutes of healthy history
    # ---------------------------------------------------------
    for minute in range(10):
        reading = make_reading(
            timestamp=start + timedelta(minutes=minute),
            value=0.0,
            occupancy=0,
        )
        result = pipeline.process_reading(reading)

    # ---------------------------------------------------------
    # 2. Inject 12 minutes of continuous flow
    #    while occupancy is zero.
    #
    #    The configured leak duration is 10 minutes.
    # ---------------------------------------------------------
    for minute in range(12):
        reading = make_reading(
            timestamp=start + timedelta(minutes=10 + minute),
            value=3.5,
            occupancy=0,
        )
        result = pipeline.process_reading(reading)

    assert result is not None

    # ---------------------------------------------------------
    # 3. Rule engine should detect the continuous leak
    # ---------------------------------------------------------
    assert result.rule_event is not None
    assert result.rule_event.anomaly_type.value == "continuous_leak"

    # ---------------------------------------------------------
    # 4. Fusion should classify the reading as anomalous
    # ---------------------------------------------------------
    assert result.fusion_result.decision.value in {
        "rule_anomaly",
        "high_confidence_anomaly",
    }

    # ---------------------------------------------------------
    # 5. Sustainability impact should be calculated
    # ---------------------------------------------------------
    assert result.sustainability_impact is not None
    assert result.sustainability_impact.litres_wasted > 0

    # ---------------------------------------------------------
    # 6. Maintenance risk should be calculated
    # ---------------------------------------------------------
    assert result.risk_result is not None
    assert 0 <= result.risk_result.risk_score <= 100

    # ---------------------------------------------------------
    # 7. Maintenance ticket should exist
    # ---------------------------------------------------------
    assert result.maintenance_ticket is not None

    # ---------------------------------------------------------
    # 8. Anomaly history should contain the event
    # ---------------------------------------------------------
    assert len(pipeline.anomaly_history) >= 1