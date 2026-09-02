"""Repository operations for storing topology and telemetry."""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import desc, select
from sqlalchemy.orm import sessionmaker

from schemas.telemetry import SensorReading
from maintenance.ticket_schemas import MaintenanceTicket
from simulator.facility_topology import (
    FacilityDefinition,
    FixtureDefinition,
    SensorDefinition,
    ZoneDefinition,
)

from .models import (
    FacilityModel,
    FixtureModel,
    MaintenanceTicketModel,
    SensorModel,
    SensorReadingModel,
    ZoneModel,
)

if TYPE_CHECKING:
    from simulator.facility_topology import FacilityTopology


class TelemetryRepository:
    """Repository for the Phase 1 SQLite schema."""

    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def create_facility(self, facility: FacilityDefinition) -> None:
        with self._session_factory() as session:
            if session.get(FacilityModel, facility.facility_id) is None:
                session.add(
                    FacilityModel(
                        facility_id=facility.facility_id,
                        name=facility.name,
                        facility_type=facility.facility_type,
                    )
                )
                session.commit()

    def create_zone(self, zone: ZoneDefinition) -> None:
        with self._session_factory() as session:
            if session.get(ZoneModel, zone.zone_id) is None:
                session.add(
                    ZoneModel(
                        zone_id=zone.zone_id,
                        facility_id=zone.facility_id,
                        name=zone.name,
                        zone_type=zone.zone_type,
                        capacity=zone.capacity,
                    )
                )
                session.commit()

    def create_fixture(self, fixture: FixtureDefinition) -> None:
        with self._session_factory() as session:
            if session.get(FixtureModel, fixture.fixture_id) is None:
                session.add(
                    FixtureModel(
                        fixture_id=fixture.fixture_id,
                        zone_id=fixture.zone_id,
                        fixture_type=fixture.fixture_type,
                        installation_age=fixture.installation_age,
                        expected_lifetime_cycles=fixture.expected_lifetime_cycles,
                    )
                )
                session.commit()

    def create_sensor(self, sensor: SensorDefinition) -> None:
        with self._session_factory() as session:
            if session.get(SensorModel, sensor.sensor_id) is None:
                session.add(
                    SensorModel(
                        sensor_id=sensor.sensor_id,
                        fixture_id=sensor.fixture_id,
                        zone_id=sensor.zone_id,
                        facility_id=sensor.facility_id,
                        sensor_type=sensor.sensor_type,
                        unit=sensor.unit,
                    )
                )
                session.commit()

    def register_topology(self, topology: FacilityTopology) -> None:
        self.create_facility(topology.facility)
        for zone in topology.zones:
            self.create_zone(zone)
        for fixture in topology.fixtures:
            self.create_fixture(fixture)
        for sensor in topology.sensors:
            self.create_sensor(sensor)

    def save_sensor_reading(self, reading: SensorReading) -> None:
        with self._session_factory() as session:
            session.add(self._build_sensor_reading_model(reading))
            session.commit()

    def save_sensor_readings(self, readings: Iterable[SensorReading]) -> None:
        with self._session_factory() as session:
            session.add_all(
                [self._build_sensor_reading_model(reading) for reading in readings]
            )
            session.commit()

    def save_maintenance_ticket(self, ticket: MaintenanceTicket) -> None:
        """Persist a maintenance ticket."""

        with self._session_factory() as session:
            existing = session.get(
                MaintenanceTicketModel,
                ticket.ticket_id,
            )

            if existing is None:
                session.add(
                    self._build_maintenance_ticket_model(ticket)
                )
            else:
                self._update_maintenance_ticket_model(
                    existing,
                    ticket,
                )

            session.commit()

    def get_maintenance_ticket(
        self,
        ticket_id: str,
    ) -> MaintenanceTicket | None:
        """Retrieve one maintenance ticket by ID."""

        with self._session_factory() as session:
            row = session.get(
                MaintenanceTicketModel,
                ticket_id,
            )

            if row is None:
                return None

            return self._maintenance_ticket_to_schema(row)

    def get_open_maintenance_tickets(
        self,
    ) -> list[MaintenanceTicket]:
        """Retrieve all active maintenance tickets."""

        with self._session_factory() as session:
            statement = (
                select(MaintenanceTicketModel)
                .where(
                    MaintenanceTicketModel.status.notin_(
                        ["resolved", "cancelled"]
                    )
                )
                .order_by(MaintenanceTicketModel.created_at)
            )

            rows = session.scalars(statement).all()

            return [
                self._maintenance_ticket_to_schema(row)
                for row in rows
            ]

    def get_maintenance_ticket_history(
        self,
        limit: int = 100,
    ) -> list[MaintenanceTicket]:
        """Retrieve maintenance ticket history."""

        with self._session_factory() as session:
            statement = (
                select(MaintenanceTicketModel)
                .order_by(
                    desc(MaintenanceTicketModel.created_at)
                )
                .limit(limit)
            )

            rows = session.scalars(statement).all()

            return [
                self._maintenance_ticket_to_schema(row)
                for row in rows
            ]

    def get_recent_readings(self, limit: int = 100) -> list[SensorReading]:
        with self._session_factory() as session:
            statement = (
                select(SensorReadingModel)
                .order_by(desc(SensorReadingModel.timestamp), desc(SensorReadingModel.id))
                .limit(limit)
            )
            rows = session.scalars(statement).all()
            return [self._to_schema(row) for row in rows]

    def get_readings_for_fixture(
        self,
        fixture_id: str,
        limit: int = 100,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[SensorReading]:
        with self._session_factory() as session:
            statement = (
                select(SensorReadingModel)
                .where(SensorReadingModel.fixture_id == fixture_id)
                .order_by(SensorReadingModel.timestamp)
                .limit(limit)
            )
            if start_time is not None:
                statement = statement.where(SensorReadingModel.timestamp >= start_time)
            if end_time is not None:
                statement = statement.where(SensorReadingModel.timestamp <= end_time)
            rows = session.scalars(statement).all()
            return [self._to_schema(row) for row in rows]

    @staticmethod
    def _build_sensor_reading_model(reading: SensorReading) -> SensorReadingModel:
        return SensorReadingModel(
            sensor_id=reading.sensor_id,
            fixture_id=reading.fixture_id,
            zone_id=reading.zone_id,
            facility_id=reading.facility_id,
            timestamp=reading.timestamp,
            sensor_type=reading.sensor_type,
            value=float(reading.value),
            unit=reading.unit,
            diagnostic_status=reading.diagnostic_status,
            quality_flag=reading.quality_flag,
            metadata_json=json.dumps(reading.metadata, sort_keys=True),
        )

    @staticmethod
    def _to_schema(row: SensorReadingModel) -> SensorReading:
        return SensorReading(
            sensor_id=row.sensor_id,
            fixture_id=row.fixture_id,
            zone_id=row.zone_id,
            facility_id=row.facility_id,
            timestamp=row.timestamp,
            sensor_type=row.sensor_type,
            value=row.value,
            unit=row.unit,
            diagnostic_status=row.diagnostic_status,
            quality_flag=row.quality_flag,
            metadata=json.loads(row.metadata_json),
        )

    @staticmethod
    def _build_maintenance_ticket_model(
        ticket: MaintenanceTicket,
    ) -> MaintenanceTicketModel:
        return MaintenanceTicketModel(
            ticket_id=ticket.ticket_id,
            facility_id=ticket.facility_id,
            zone_id=ticket.zone_id,
            fixture_id=ticket.fixture_id,
            anomaly_type=ticket.anomaly_type,
            source_event_id=ticket.source_event_id,
            priority=ticket.priority.value,
            risk_score=float(ticket.risk_score),
            title=ticket.title,
            description=ticket.description,
            recommended_action=ticket.recommended_action,
            created_at=ticket.created_at,
            status=ticket.status.value,
            evidence_json=json.dumps(
                ticket.evidence,
                sort_keys=True,
            ),
            deduplication_key=ticket.deduplication_key,
        )

    @staticmethod
    def _update_maintenance_ticket_model(
        row: MaintenanceTicketModel,
        ticket: MaintenanceTicket,
    ) -> None:
        row.facility_id = ticket.facility_id
        row.zone_id = ticket.zone_id
        row.fixture_id = ticket.fixture_id
        row.anomaly_type = ticket.anomaly_type
        row.source_event_id = ticket.source_event_id
        row.priority = ticket.priority.value
        row.risk_score = float(ticket.risk_score)
        row.title = ticket.title
        row.description = ticket.description
        row.recommended_action = ticket.recommended_action
        row.created_at = ticket.created_at
        row.status = ticket.status.value
        row.evidence_json = json.dumps(
            ticket.evidence,
            sort_keys=True,
        )
        row.deduplication_key = ticket.deduplication_key

    @staticmethod
    def _maintenance_ticket_to_schema(
        row: MaintenanceTicketModel,
    ) -> MaintenanceTicket:
        return MaintenanceTicket(
            ticket_id=row.ticket_id,
            facility_id=row.facility_id,
            zone_id=row.zone_id,
            fixture_id=row.fixture_id,
            anomaly_type=row.anomaly_type,
            source_event_id=row.source_event_id,
            priority=row.priority,
            risk_score=row.risk_score,
            title=row.title,
            description=row.description,
            recommended_action=row.recommended_action,
            created_at=row.created_at,
            status=row.status,
            evidence=json.loads(row.evidence_json),
            deduplication_key=row.deduplication_key,
        )