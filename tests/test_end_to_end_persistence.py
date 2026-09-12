from pathlib import Path

from database.db import create_session_factory, init_db
from database.repository import TelemetryRepository
from simulator.simulation_engine import SimulationEngine


def test_simulator_pipeline_persists_sustainability_ticket(tmp_path: Path):
    database_path = tmp_path / "end_to_end.db"

    engine = SimulationEngine(
        preset_name="airport",
        database_path=database_path,
        tick_minutes=1,
        seed=42,
    )

    try:
        # Build a short healthy history first.
        for _ in range(5):
            engine.run_tick(persist=True)

        # Use the first fixture as the controlled test target.
        target_fixture = engine.topology.fixtures[0].fixture_id

        # Inject a sustained high-severity leak.
        engine.inject_fault(
            fault_type="continuous_leak",
            duration_minutes=15,
            severity="high",
            fixture_id=target_fixture,
        )

        # Run until the leak is detected and persisted.
        for _ in range(15):
            engine.run_tick(persist=True)

    finally:
        engine.stop()

    # Read the database exactly like the dashboard does.
    init_db(database_path)
    repository = TelemetryRepository(
        create_session_factory(database_path)
    )

    tickets = repository.get_open_maintenance_tickets()

    assert tickets, "No maintenance ticket was persisted."

    leak_tickets = [
        ticket
        for ticket in tickets
        if ticket.anomaly_type == "continuous_leak"
    ]

    assert leak_tickets, "No continuous-leak ticket was persisted."

    ticket = leak_tickets[0]

    assert ticket.evidence is not None

    sustainability = ticket.evidence.get(
        "sustainability_impact"
    )

    assert sustainability is not None

    assert sustainability["litres_wasted"] > 0
    assert sustainability["potential_litres_saved"] > 0
    assert sustainability["estimated_cost"] > 0
    assert sustainability["potential_cost_saving"] > 0