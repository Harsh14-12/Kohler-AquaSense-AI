from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class TicketPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TicketStatus(str, Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"


class MaintenanceTicket(BaseModel):
    """Maintenance ticket generated from an anomaly and risk assessment."""

    ticket_id: str
    facility_id: str
    zone_id: str
    fixture_id: str

    anomaly_type: str
    source_event_id: str

    priority: TicketPriority
    risk_score: float = Field(ge=0.0, le=100.0)

    title: str
    description: str
    recommended_action: str

    created_at: datetime
    status: TicketStatus = TicketStatus.OPEN

    evidence: dict[str, object]
    deduplication_key: str