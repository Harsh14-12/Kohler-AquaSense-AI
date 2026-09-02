from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base
from database.repository import TelemetryRepository
from detection.schemas import (
    AnomalyEvent,
    AnomalySeverity,
    AnomalyStatus,
    AnomalyType,
)
from maintenance.risk_engine import (
    MaintenanceRiskLevel,
    MaintenanceRiskResult,
)
from maintenance.ticket_engine import MaintenanceTicketEngine


def make_event():
    return AnomalyEvent(
        event_id="EVT-DB-001",
        facility_id="airport_01",
        zone_id="restroom_a",
        fixture_id="toilet_01",
        timestamp=datetime(
            2026,
            9,
            1,
            10,
            0,
            tzinfo=timezone.utc,
        ),
        anomaly_type=AnomalyType.CONTINUOUS_LEAK,
        severity=AnomalySeverity.HIGH,
        confidence=0.92,
        status=AnomalyStatus.OPEN,
        triggered_rules=[
            "continuous_flow_while_unoccupied"
        ],
        triggering_features=[
            "current_flow_rate",
            "occupancy",
        ],
        observed_value=3.5,
        expected_value=0.0,
        explanation=(
            "Continuous water flow detected while unoccupied."
        ),
        explanation_trace={
            "rule": "continuous_flow_while_unoccupied",
            "observations": {
                "flow_rate_l_per_min": 3.5,
                "occupancy": 0.0,
            },
            "expected": {
                "flow_rate_l_per_min": 0.0,
            },
            "thresholds": {
                "leak_flow_threshold": 0.5,
            },
            "feature_deltas": {
                "flow_excess": 3.5,
            },
        },
    )


def make_risk():
    return MaintenanceRiskResult(
        fixture_id="toilet_01",
        risk_score=65.0,
        risk_level=MaintenanceRiskLevel.HIGH,
        contributing_factors={
            "recent_anomaly_recurrence": 1.0,
            "persistent_abnormal_flow": 1.0,
        },
        recommended_action=(
            "Create priority maintenance ticket."
        ),
        explanation=(
            "High maintenance risk due to recurring "
            "abnormal behavior."
        ),
    )


def create_repository():
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
    )

    Base.metadata.create_all(engine)

    session_factory = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    return TelemetryRepository(session_factory)


def test_save_and_get_ticket():
    repository = create_repository()

    ticket_engine = MaintenanceTicketEngine()

    ticket, created = ticket_engine.create_or_get_ticket(
        make_event(),
        make_risk(),
    )

    assert created is True

    repository.save_maintenance_ticket(ticket)

    loaded = repository.get_maintenance_ticket(
        ticket.ticket_id
    )

    assert loaded is not None
    assert loaded.ticket_id == ticket.ticket_id
    assert loaded.facility_id == "airport_01"
    assert loaded.fixture_id == "toilet_01"
    assert loaded.priority.value == "high"
    assert loaded.risk_score == 65.0


def test_ticket_evidence_survives_database_round_trip():
    repository = create_repository()

    ticket_engine = MaintenanceTicketEngine()

    ticket, _ = ticket_engine.create_or_get_ticket(
        make_event(),
        make_risk(),
    )

    repository.save_maintenance_ticket(ticket)

    loaded = repository.get_maintenance_ticket(
        ticket.ticket_id
    )

    assert loaded is not None
    assert loaded.evidence["source_event_id"] == "EVT-DB-001"
    assert loaded.evidence["risk_score"] == 65.0


def test_open_ticket_query():
    repository = create_repository()

    ticket_engine = MaintenanceTicketEngine()

    ticket, _ = ticket_engine.create_or_get_ticket(
        make_event(),
        make_risk(),
    )

    repository.save_maintenance_ticket(ticket)

    open_tickets = repository.get_open_maintenance_tickets()

    assert len(open_tickets) == 1
    assert open_tickets[0].ticket_id == ticket.ticket_id


def test_resolved_ticket_not_returned_as_open():
    repository = create_repository()

    ticket_engine = MaintenanceTicketEngine()

    ticket, _ = ticket_engine.create_or_get_ticket(
        make_event(),
        make_risk(),
    )

    repository.save_maintenance_ticket(ticket)

    resolved = ticket_engine.resolve_ticket(
        ticket.ticket_id
    )

    repository.save_maintenance_ticket(resolved)

    open_tickets = repository.get_open_maintenance_tickets()

    assert len(open_tickets) == 0

    history = repository.get_maintenance_ticket_history()

    assert len(history) == 1
    assert history[0].status.value == "resolved"


def test_ticket_update_is_persisted():
    repository = create_repository()

    ticket_engine = MaintenanceTicketEngine()

    ticket, _ = ticket_engine.create_or_get_ticket(
        make_event(),
        make_risk(),
    )

    repository.save_maintenance_ticket(ticket)

    acknowledged = ticket_engine.acknowledge_ticket(
        ticket.ticket_id
    )

    repository.save_maintenance_ticket(acknowledged)

    loaded = repository.get_maintenance_ticket(
        ticket.ticket_id
    )

    assert loaded is not None
    assert loaded.status.value == "acknowledged"