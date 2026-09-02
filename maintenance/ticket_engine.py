from __future__ import annotations

from datetime import datetime, timezone

from detection.schemas import AnomalyEvent
from maintenance.risk_engine import MaintenanceRiskResult
from maintenance.ticket_schemas import (
    MaintenanceTicket,
    TicketPriority,
    TicketStatus,
)


class MaintenanceTicketEngine:
    """Creates, deduplicates, tracks, and resolves maintenance tickets."""

    def __init__(self) -> None:
        self._active_tickets: dict[str, MaintenanceTicket] = {}
        self._ticket_history: list[MaintenanceTicket] = []
        self._counter = 0

    def _next_ticket_id(self) -> str:
        self._counter += 1
        return f"TKT-{self._counter:04d}"

    @staticmethod
    def _priority_from_risk(
        risk: MaintenanceRiskResult,
        event: AnomalyEvent,
    ) -> TicketPriority:
        """Convert risk level and anomaly severity into ticket priority."""

        risk_level = risk.risk_level.value.lower()
        severity = event.severity.value.lower()

        if risk_level == "critical" or severity == "critical":
            return TicketPriority.CRITICAL

        if risk_level == "high" or severity == "high":
            return TicketPriority.HIGH

        if risk_level == "medium" or severity == "medium":
            return TicketPriority.MEDIUM

        return TicketPriority.LOW

    @staticmethod
    def _deduplication_key(event: AnomalyEvent) -> str:
        return (
            f"{event.facility_id}:"
            f"{event.zone_id}:"
            f"{event.fixture_id}:"
            f"{event.anomaly_type.value}"
        )

    @staticmethod
    def _build_title(event: AnomalyEvent) -> str:
        anomaly_name = event.anomaly_type.value.replace("_", " ").title()
        return f"{anomaly_name} detected on fixture {event.fixture_id}"

    @staticmethod
    def _build_description(
        event: AnomalyEvent,
        risk: MaintenanceRiskResult,
    ) -> str:
        anomaly_name = event.anomaly_type.value.replace("_", " ")

        return (
            f"A {anomaly_name} anomaly was detected in zone "
            f"{event.zone_id} on fixture {event.fixture_id}. "
            f"The anomaly has a confidence of "
            f"{event.confidence:.2f} and the calculated maintenance "
            f"risk score is {risk.risk_score:.1f}/100."
        )

    @staticmethod
    def _build_evidence(
        event: AnomalyEvent,
        risk: MaintenanceRiskResult,
    ) -> dict[str, str | float | bool]:
        evidence: dict[str, str | float | bool] = {
            "source_event_id": event.event_id,
            "anomaly_type": event.anomaly_type.value,
            "severity": event.severity.value,
            "anomaly_confidence": event.confidence,
            "risk_score": risk.risk_score,
            "risk_level": risk.risk_level.value,
        }

        if event.explanation:
            evidence["explanation"] = event.explanation

        return evidence

    def create_or_get_ticket(
        self,
        event: AnomalyEvent,
        risk: MaintenanceRiskResult,
        created_at: datetime | None = None,
    ) -> tuple[MaintenanceTicket, bool]:
        """
        Create a ticket unless an active ticket already exists
        for the same facility, zone, fixture, and anomaly type.

        Returns:
            (ticket, created)
        """

        dedup_key = self._deduplication_key(event)

        existing = self._active_tickets.get(dedup_key)

        if existing is not None:
            return existing, False

        if created_at is None:
            created_at = datetime.now(timezone.utc)

        priority = self._priority_from_risk(risk, event)

        ticket = MaintenanceTicket(
            ticket_id=self._next_ticket_id(),
            facility_id=event.facility_id,
            zone_id=event.zone_id,
            fixture_id=event.fixture_id,
            anomaly_type=event.anomaly_type.value,
            source_event_id=event.event_id,
            priority=priority,
            risk_score=risk.risk_score,
            title=self._build_title(event),
            description=self._build_description(event, risk),
            recommended_action=risk.recommended_action,
            created_at=created_at,
            status=TicketStatus.OPEN,
            evidence=self._build_evidence(event, risk),
            deduplication_key=dedup_key,
        )

        self._active_tickets[dedup_key] = ticket
        self._ticket_history.append(ticket)

        return ticket, True

    def acknowledge_ticket(self, ticket_id: str) -> MaintenanceTicket:
        ticket = self._find_active_ticket(ticket_id)

        updated = ticket.copy(
            update={"status": TicketStatus.ACKNOWLEDGED}
        )

        self._replace_active_ticket(updated)
        self._replace_history_ticket(updated)

        return updated

    def start_ticket(self, ticket_id: str) -> MaintenanceTicket:
        ticket = self._find_active_ticket(ticket_id)

        updated = ticket.copy(
            update={"status": TicketStatus.IN_PROGRESS}
        )

        self._replace_active_ticket(updated)
        self._replace_history_ticket(updated)

        return updated

    def resolve_ticket(self, ticket_id: str) -> MaintenanceTicket:
        ticket = self._find_active_ticket(ticket_id)

        updated = ticket.copy(
            update={"status": TicketStatus.RESOLVED}
        )

        self._active_tickets.pop(ticket.deduplication_key, None)
        self._replace_history_ticket(updated)

        return updated

    def cancel_ticket(self, ticket_id: str) -> MaintenanceTicket:
        ticket = self._find_active_ticket(ticket_id)

        updated = ticket.copy(
            update={"status": TicketStatus.CANCELLED}
        )

        self._active_tickets.pop(ticket.deduplication_key, None)
        self._replace_history_ticket(updated)

        return updated

    def get_open_tickets(self) -> list[MaintenanceTicket]:
        return list(self._active_tickets.values())

    def get_ticket_history(self) -> list[MaintenanceTicket]:
        return list(self._ticket_history)

    def _find_active_ticket(self, ticket_id: str) -> MaintenanceTicket:
        for ticket in self._active_tickets.values():
            if ticket.ticket_id == ticket_id:
                return ticket

        raise KeyError(f"Active ticket not found: {ticket_id}")

    def _replace_active_ticket(self, ticket: MaintenanceTicket) -> None:
        self._active_tickets[ticket.deduplication_key] = ticket

    def _replace_history_ticket(self, ticket: MaintenanceTicket) -> None:
        for index, existing in enumerate(self._ticket_history):
            if existing.ticket_id == ticket.ticket_id:
                self._ticket_history[index] = ticket
                return