from pathlib import Path

from app.pipeline import AquaSensePipeline
from simulator.simulation_engine import SimulationEngine


def test_simulator_feeds_aquasense_pipeline(tmp_path: Path):
    database_path = tmp_path / "simulator_pipeline.db"

    simulator = SimulationEngine(
        preset_name="airport",
        database_path=database_path,
        tick_minutes=1,
        seed=42,
    )

    pipeline = AquaSensePipeline()

    for _ in range(5):
        tick_result = simulator.run_tick(persist=False)

        assert tick_result.readings

        for reading in tick_result.readings:
            result = pipeline.process_reading(reading)

            assert result.feature_vector is not None

    simulator.stop()