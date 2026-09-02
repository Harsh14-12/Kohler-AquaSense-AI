from datetime import datetime, timezone

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
from maintenance.ticket_schemas import TicketPriority, TicketStatus


def make_event(
    anomaly_type=AnomalyType.CONTINUOUS_LEAK,
    severity=AnomalySeverity.HIGH,
    event_id="EVT-001",
):
    return AnomalyEvent(
        event_id=event_id,
        facility_id="airport_01",
        zone_id="restroom_a",
        fixture_id="toilet_01",
        timestamp=datetime(
            2026, 9, 1, 10, 0, tzinfo=timezone.utc
        ),
        anomaly_type=anomaly_type,
        severity=severity,
        confidence=0.92,
        status=AnomalyStatus.OPEN,
        triggered_rules=["continuous_flow_while_unoccupied"],
        triggering_features=["current_flow_rate", "occupancy"],
        observed_value=3.5,
        expected_value=0.0,
        explanation="Continuous water flow detected while unoccupied.",
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


def make_risk(
    score=65.0,
    level=MaintenanceRiskLevel.HIGH,
):
    return MaintenanceRiskResult(
        fixture_id="toilet_01",
        risk_score=score,
        risk_level=level,
        contributing_factors={
            "recent anomaly recurrence": 1.0,
            "persistent abnormal flow": 1.0,
        },
        recommended_action="Create priority maintenance ticket.",
        explanation="High maintenance risk due to recurring abnormal behavior.",
    )


def test_ticket_is_created():
    engine = MaintenanceTicketEngine()

    ticket, created = engine.create_or_get_ticket(
        make_event(),
        make_risk(),
    )

    assert created is True
    assert ticket.ticket_id == "TKT-0001"
    assert ticket.facility_id == "airport_01"
    assert ticket.zone_id == "restroom_a"
    assert ticket.fixture_id == "toilet_01"
    assert ticket.status == TicketStatus.OPEN


def test_high_risk_creates_high_priority_ticket():
    engine = MaintenanceTicketEngine()

    ticket, _ = engine.create_or_get_ticket(
        make_event(),
        make_risk(65.0, MaintenanceRiskLevel.HIGH),
    )

    assert ticket.priority == TicketPriority.HIGH


def test_critical_risk_creates_critical_ticket():
    engine = MaintenanceTicketEngine()

    event = make_event(severity=AnomalySeverity.MEDIUM)

    ticket, _ = engine.create_or_get_ticket(
        event,
        make_risk(90.0, MaintenanceRiskLevel.CRITICAL),
    )

    assert ticket.priority == TicketPriority.CRITICAL


def test_same_active_anomaly_is_deduplicated():
    engine = MaintenanceTicketEngine()

    event1 = make_event(event_id="EVT-001")
    event2 = make_event(event_id="EVT-002")

    ticket1, created1 = engine.create_or_get_ticket(
        event1,
        make_risk(),
    )

    ticket2, created2 = engine.create_or_get_ticket(
        event2,
        make_risk(),
    )

    assert created1 is True
    assert created2 is False
    assert ticket1.ticket_id == ticket2.ticket_id
    assert len(engine.get_open_tickets()) == 1


def test_different_anomaly_types_get_separate_tickets():
    engine = MaintenanceTicketEngine()

    leak_event = make_event(
        anomaly_type=AnomalyType.CONTINUOUS_LEAK,
        event_id="EVT-001",
    )

    ghost_flush_event = make_event(
        anomaly_type=AnomalyType.GHOST_FLUSH,
        event_id="EVT-002",
    )

    ticket1, created1 = engine.create_or_get_ticket(
        leak_event,
        make_risk(),
    )

    ticket2, created2 = engine.create_or_get_ticket(
        ghost_flush_event,
        make_risk(),
    )

    assert created1 is True
    assert created2 is True
    assert ticket1.ticket_id != ticket2.ticket_id
    assert len(engine.get_open_tickets()) == 2


def test_resolved_ticket_allows_new_recurrence():
    engine = MaintenanceTicketEngine()

    first_event = make_event(event_id="EVT-001")

    first_ticket, created = engine.create_or_get_ticket(
        first_event,
        make_risk(),
    )

    assert created is True

    resolved = engine.resolve_ticket(first_ticket.ticket_id)

    assert resolved.status == TicketStatus.RESOLVED
    assert len(engine.get_open_tickets()) == 0

    second_event = make_event(event_id="EVT-002")

    second_ticket, created_again = engine.create_or_get_ticket(
        second_event,
        make_risk(),
    )

    assert created_again is True
    assert second_ticket.ticket_id != first_ticket.ticket_id
    assert len(engine.get_ticket_history()) == 2


def test_ticket_lifecycle():
    engine = MaintenanceTicketEngine()

    ticket, _ = engine.create_or_get_ticket(
        make_event(),
        make_risk(),
    )

    acknowledged = engine.acknowledge_ticket(ticket.ticket_id)
    assert acknowledged.status == TicketStatus.ACKNOWLEDGED

    started = engine.start_ticket(ticket.ticket_id)
    assert started.status == TicketStatus.IN_PROGRESS

    resolved = engine.resolve_ticket(ticket.ticket_id)
    assert resolved.status == TicketStatus.RESOLVED


def test_ticket_contains_evidence():
    engine = MaintenanceTicketEngine()

    ticket, _ = engine.create_or_get_ticket(
        make_event(),
        make_risk(),
    )

    assert ticket.evidence["source_event_id"] == "EVT-001"
    assert ticket.evidence["anomaly_type"] == "continuous_leak"
    assert ticket.evidence["risk_score"] == 65.0
    assert ticket.evidence["severity"] == "high"


def test_ticket_history_keeps_resolved_tickets():
    engine = MaintenanceTicketEngine()

    ticket, _ = engine.create_or_get_ticket(
        make_event(),
        make_risk(),
    )

    engine.resolve_ticket(ticket.ticket_id)

    history = engine.get_ticket_history()

    assert len(history) == 1
    assert history[0].status == TicketStatus.RESOLVED