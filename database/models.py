"""SQLAlchemy ORM models for the Phase 1 simulator."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for ORM models."""


class FacilityModel(Base):
    __tablename__ = "facility"

    facility_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    facility_type: Mapped[str] = mapped_column(String(64), nullable=False)

    zones: Mapped[list["ZoneModel"]] = relationship(back_populates="facility")


class ZoneModel(Base):
    __tablename__ = "zone"

    zone_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    facility_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("facility.facility_id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    zone_type: Mapped[str] = mapped_column(String(64), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)

    facility: Mapped[FacilityModel] = relationship(back_populates="zones")
    fixtures: Mapped[list["FixtureModel"]] = relationship(back_populates="zone")


class FixtureModel(Base):
    __tablename__ = "fixture"

    fixture_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    zone_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("zone.zone_id"), nullable=False
    )
    fixture_type: Mapped[str] = mapped_column(String(64), nullable=False)
    installation_age: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_lifetime_cycles: Mapped[int] = mapped_column(Integer, nullable=False)

    zone: Mapped[ZoneModel] = relationship(back_populates="fixtures")
    sensors: Mapped[list["SensorModel"]] = relationship(back_populates="fixture")


class SensorModel(Base):
    __tablename__ = "sensor"

    sensor_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    fixture_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("fixture.fixture_id"), nullable=False
    )
    zone_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("zone.zone_id"), nullable=False
    )
    facility_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("facility.facility_id"), nullable=False
    )
    sensor_type: Mapped[str] = mapped_column(String(64), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)

    fixture: Mapped[FixtureModel] = relationship(back_populates="sensors")
    readings: Mapped[list["SensorReadingModel"]] = relationship(back_populates="sensor")


class SensorReadingModel(Base):
    __tablename__ = "sensor_reading"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sensor_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("sensor.sensor_id"), nullable=False, index=True
    )
    fixture_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    zone_id: Mapped[str] = mapped_column(String(128), nullable=False)
    facility_id: Mapped[str] = mapped_column(String(128), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    sensor_type: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    diagnostic_status: Mapped[str] = mapped_column(String(32), nullable=False)
    quality_flag: Mapped[str] = mapped_column(String(32), nullable=False)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    sensor: Mapped[SensorModel] = relationship(back_populates="readings")

class MaintenanceTicketModel(Base):
    __tablename__ = "maintenance_ticket"

    ticket_id: Mapped[str] = mapped_column(String(128), primary_key=True)

    facility_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("facility.facility_id"), nullable=False, index=True
    )
    zone_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("zone.zone_id"), nullable=False, index=True
    )
    fixture_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("fixture.fixture_id"), nullable=False, index=True
    )

    anomaly_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_event_id: Mapped[str] = mapped_column(String(128), nullable=False)

    priority: Mapped[str] = mapped_column(String(32), nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)

    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_action: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, index=True
    )

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True
    )

    evidence_json: Mapped[str] = mapped_column(
        Text, nullable=False, default="{}"
    )

    deduplication_key: Mapped[str] = mapped_column(
        String(256), nullable=False, index=True
    )
