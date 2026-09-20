"""Grounded data-access tools for the AquaSense AI Copilot."""

from __future__ import annotations

from typing import Any

from database.repository import TelemetryRepository

from .schemas import CopilotEvidence


class AquaSenseCopilotTools:
    """
    Read-only tools exposing existing AquaSense operational evidence.

    The Copilot must use these tools instead of inventing facility facts.
    """

    def __init__(self, repository: TelemetryRepository) -> None:
        self.repository = repository

    def get_open_maintenance_tickets(
        self,
    ) -> CopilotEvidence:
        """Return currently active maintenance tickets."""

        tickets = self.repository.get_open_maintenance_tickets()

        data: list[dict[str, Any]] = []

        for ticket in tickets:
            data.append(
                {
                    "ticket_id": ticket.ticket_id,
                    "facility_id": ticket.facility_id,
                    "zone_id": ticket.zone_id,
                    "fixture_id": ticket.fixture_id,
                    "anomaly_type": ticket.anomaly_type,
                    "priority": ticket.priority.value,
                    "risk_score": ticket.risk_score,
                    "title": ticket.title,
                    "description": ticket.description,
                    "recommended_action": ticket.recommended_action,
                    "created_at": ticket.created_at.isoformat(),
                    "status": ticket.status.value,
                    "evidence": ticket.evidence,
                }
            )

        return CopilotEvidence(
            source="maintenance_tickets",
            data={
                "count": len(data),
                "tickets": data,
            },
        )

    def get_recent_readings(
        self,
        limit: int = 50,
    ) -> CopilotEvidence:
        """Return recent persisted telemetry readings."""

        if limit < 1:
            raise ValueError("limit must be at least 1")

        readings = self.repository.get_recent_readings(limit=limit)

        data: list[dict[str, Any]] = []

        for reading in readings:
            data.append(
                {
                    "sensor_id": reading.sensor_id,
                    "fixture_id": reading.fixture_id,
                    "zone_id": reading.zone_id,
                    "facility_id": reading.facility_id,
                    "timestamp": reading.timestamp.isoformat(),
                    "sensor_type": (
                        reading.sensor_type.value
                        if hasattr(reading.sensor_type, "value")
                        else str(reading.sensor_type)
                    ),
                    "value": float(reading.value),
                    "unit": reading.unit,
                    "diagnostic_status": (
                        reading.diagnostic_status.value
                        if hasattr(reading.diagnostic_status, "value")
                        else str(reading.diagnostic_status)
                    ),
                    "quality_flag": (
                        reading.quality_flag.value
                        if hasattr(reading.quality_flag, "value")
                        else str(reading.quality_flag)
                    ),
                    "metadata": reading.metadata,
                }
            )

        return CopilotEvidence(
            source="recent_telemetry",
            data={
                "count": len(data),
                "readings": data,
            },
        )

    def get_fixture_readings(
        self,
        fixture_id: str,
        limit: int = 100,
    ) -> CopilotEvidence:
        """Return persisted telemetry for one fixture."""

        if not fixture_id:
            raise ValueError("fixture_id must not be empty")

        if limit < 1:
            raise ValueError("limit must be at least 1")

        readings = self.repository.get_readings_for_fixture(
            fixture_id=fixture_id,
            limit=limit,
        )

        data: list[dict[str, Any]] = []

        for reading in readings:
            data.append(
                {
                    "sensor_id": reading.sensor_id,
                    "fixture_id": reading.fixture_id,
                    "zone_id": reading.zone_id,
                    "facility_id": reading.facility_id,
                    "timestamp": reading.timestamp.isoformat(),
                    "sensor_type": (
                        reading.sensor_type.value
                        if hasattr(reading.sensor_type, "value")
                        else str(reading.sensor_type)
                    ),
                    "value": float(reading.value),
                    "unit": reading.unit,
                    "diagnostic_status": (
                        reading.diagnostic_status.value
                        if hasattr(reading.diagnostic_status, "value")
                        else str(reading.diagnostic_status)
                    ),
                    "quality_flag": (
                        reading.quality_flag.value
                        if hasattr(reading.quality_flag, "value")
                        else str(reading.quality_flag)
                    ),
                    "metadata": reading.metadata,
                }
            )

        return CopilotEvidence(
            source="fixture_telemetry",
            data={
                "fixture_id": fixture_id,
                "count": len(data),
                "readings": data,
            },
        )