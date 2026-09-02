"""Repository operations for storing topology and telemetry."""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import desc, select
from sqlalchemy.orm import sessionmaker

from schemas.telemetry import SensorReading
from simulator.facility_topology import (
    FacilityDefinition,
    FixtureDefinition,
    SensorDefinition,
    ZoneDefinition,
)

from .models import (
    FacilityModel,
    FixtureModel,
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
