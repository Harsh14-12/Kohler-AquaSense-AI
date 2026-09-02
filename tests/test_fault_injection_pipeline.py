from pathlib import Path

from app.pipeline import AquaSensePipeline
from simulator.simulation_engine import SimulationEngine


def test_continuous_leak_flows_through_aquasense_pipeline(
    tmp_path: Path,
):
    """
    Verify that a real simulator continuous-leak fault
    is detected by the complete AquaSense pipeline.
    """

    database_path = tmp_path / "fault_pipeline.db"

    simulator = SimulationEngine(
        preset_name="airport",
        database_path=database_path,
        tick_minutes=1,
        seed=42,
    )

    pipeline = AquaSensePipeline()

    try:
        # ---------------------------------------------------------
        # Run initial healthy ticks.
        # ---------------------------------------------------------
        for _ in range(5):
            tick_result = simulator.run_tick(
                persist=False
            )

            assert tick_result.readings

            for reading in tick_result.readings:
                pipeline.process_reading(reading)

        # ---------------------------------------------------------
        # Get a real fixture from the simulator telemetry.
        # ---------------------------------------------------------
        tick_result = simulator.run_tick(
            persist=False
        )

        assert tick_result.readings

        target_fixture_id = tick_result.readings[0].fixture_id

        # Feed this normal tick into the pipeline as well.
        for reading in tick_result.readings:
            pipeline.process_reading(reading)

        # ---------------------------------------------------------
        # Inject a real continuous leak.
        # ---------------------------------------------------------
        simulator.inject_fault(
            fault_type="continuous_leak",
            duration_minutes=15,
            severity="high",
            fixture_id=target_fixture_id,
        )

        leak_detected = False
        detected_result = None

        # ---------------------------------------------------------
        # Run enough simulated minutes for the
        # 10-minute leak detection rule to trigger.
        # ---------------------------------------------------------
        for _ in range(15):
            tick_result = simulator.run_tick(
                persist=False
            )

            assert tick_result.readings

            for reading in tick_result.readings:
                result = pipeline.process_reading(
                    reading
                )

                if (
                    result.rule_event is not None
                    and result.rule_event.anomaly_type.value
                    == "continuous_leak"
                ):
                    leak_detected = True
                    detected_result = result
                    break

            if leak_detected:
                break

        # ---------------------------------------------------------
        # Verify AquaSense detected the real simulator fault.
        # ---------------------------------------------------------
        assert leak_detected is True
        assert detected_result is not None

        # ---------------------------------------------------------
        # Sustainability impact must be calculated.
        # ---------------------------------------------------------
        assert detected_result.sustainability_impact is not None
        assert (
            detected_result.sustainability_impact.litres_wasted
            > 0
        )

        # ---------------------------------------------------------
        # Maintenance risk must be calculated.
        # ---------------------------------------------------------
        assert detected_result.risk_result is not None
        assert 0 <= detected_result.risk_result.risk_score <= 100

        # ---------------------------------------------------------
        # Maintenance ticket must be created.
        # ---------------------------------------------------------
        assert detected_result.maintenance_ticket is not None

    finally:
        simulator.stop()