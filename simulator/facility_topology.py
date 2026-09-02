"""Configurable facility presets for the AquaSense simulator."""

from __future__ import annotations

from dataclasses import dataclass

from schemas.telemetry import SensorType, Unit


def _fixture_mix(faucets: int, flush_valves: int, urinals: int) -> dict[str, int]:
    return {
        "faucet": faucets,
        "flush_valve": flush_valves,
        "urinal": urinals,
        "water_line": 1,
    }


@dataclass(frozen=True)
class FacilityDefinition:
    facility_id: str
    name: str
    facility_type: str


@dataclass(frozen=True)
class ZoneDefinition:
    zone_id: str
    facility_id: str
    name: str
    zone_type: str
    capacity: int


@dataclass(frozen=True)
class FixtureDefinition:
    fixture_id: str
    fixture_type: str
    zone_id: str
    installation_age: int
    expected_lifetime_cycles: int


@dataclass(frozen=True)
class SensorDefinition:
    sensor_id: str
    fixture_id: str
    zone_id: str
    facility_id: str
    sensor_type: str
    unit: str


@dataclass(frozen=True)
class ZonePreset:
    area_name: str
    zone_name: str
    zone_type: str
    capacity: int
    fixture_counts: dict[str, int]


@dataclass(frozen=True)
class FacilityPreset:
    facility_id: str
    name: str
    facility_type: str
    zones: list[ZonePreset]


@dataclass(frozen=True)
class FacilityTopology:
    facility: FacilityDefinition
    zones: list[ZoneDefinition]
    fixtures: list[FixtureDefinition]
    sensors: list[SensorDefinition]

    @property
    def zone_map(self) -> dict[str, ZoneDefinition]:
        return {zone.zone_id: zone for zone in self.zones}

    @property
    def fixture_map(self) -> dict[str, FixtureDefinition]:
        return {fixture.fixture_id: fixture for fixture in self.fixtures}

    @property
    def sensor_map(self) -> dict[str, SensorDefinition]:
        return {sensor.sensor_id: sensor for sensor in self.sensors}


PRESETS: dict[str, FacilityPreset] = {
    "airport": FacilityPreset(
        facility_id="airport_terminal",
        name="Airport Terminal",
        facility_type="airport",
        zones=[
            ZonePreset("Terminal A", "Restroom A1", "restroom_airside", 48, _fixture_mix(2, 1, 1)),
            ZonePreset("Terminal A", "Restroom A2", "restroom_airside", 42, _fixture_mix(2, 1, 1)),
            ZonePreset("Terminal A", "Restroom A3", "restroom_airside", 40, _fixture_mix(2, 1, 1)),
            ZonePreset("Terminal B", "Restroom B1", "restroom_airside", 50, _fixture_mix(2, 1, 1)),
            ZonePreset("Terminal B", "Restroom B2", "restroom_airside", 44, _fixture_mix(2, 1, 1)),
            ZonePreset("Terminal B", "Restroom B3", "restroom_airside", 38, _fixture_mix(2, 1, 1)),
        ],
    ),
    "hospital": FacilityPreset(
        facility_id="hospital_main",
        name="Hospital",
        facility_type="hospital",
        zones=[
            ZonePreset("Emergency", "Emergency Restroom", "restroom_emergency", 22, _fixture_mix(1, 1, 1)),
            ZonePreset("Outpatient", "Outpatient Restroom", "restroom_outpatient", 28, _fixture_mix(1, 1, 1)),
            ZonePreset("Ward", "Ward Restroom", "restroom_ward", 20, _fixture_mix(1, 1, 1)),
            ZonePreset("Main Building", "Lobby Restroom", "restroom_public", 24, _fixture_mix(1, 1, 1)),
        ],
    ),
    "university": FacilityPreset(
        facility_id="university_campus",
        name="University Campus",
        facility_type="university",
        zones=[
            ZonePreset("Academic Building", "Academic Restroom", "restroom_academic", 30, _fixture_mix(1, 1, 1)),
            ZonePreset("Library", "Library Restroom", "restroom_library", 24, _fixture_mix(1, 1, 1)),
            ZonePreset("Student Center", "Student Center Restroom", "restroom_student_center", 34, _fixture_mix(2, 1, 1)),
            ZonePreset("Administration", "Administration Restroom", "restroom_admin", 18, _fixture_mix(1, 1, 1)),
        ],
    ),
}


def build_facility_topology(preset_name: str) -> FacilityTopology:
    """Build a facility topology for a configured preset."""

    if preset_name not in PRESETS:
        raise ValueError(f"Unknown facility preset: {preset_name}")

    preset = PRESETS[preset_name]
    facility = FacilityDefinition(
        facility_id=preset.facility_id,
        name=preset.name,
        facility_type=preset.facility_type,
    )

    zones: list[ZoneDefinition] = []
    fixtures: list[FixtureDefinition] = []
    sensors: list[SensorDefinition] = []

    for zone_index, zone_preset in enumerate(preset.zones, start=1):
        zone_slug = _slugify(f"{zone_preset.area_name}-{zone_preset.zone_name}")
        zone_id = f"{preset.facility_id}-{zone_slug}"
        zone = ZoneDefinition(
            zone_id=zone_id,
            facility_id=facility.facility_id,
            name=f"{zone_preset.area_name} / {zone_preset.zone_name}",
            zone_type=zone_preset.zone_type,
            capacity=zone_preset.capacity,
        )
        zones.append(zone)

        for fixture_type, count in zone_preset.fixture_counts.items():
            for fixture_number in range(1, count + 1):
                fixture_id = (
                    f"{zone_id}-{fixture_type.replace('_', '-')}-{fixture_number:02d}"
                )
                fixture = FixtureDefinition(
                    fixture_id=fixture_id,
                    fixture_type=fixture_type,
                    zone_id=zone_id,
                    installation_age=_installation_age(zone_index, fixture_number),
                    expected_lifetime_cycles=_expected_lifetime_cycles(fixture_type),
                )
                fixtures.append(fixture)
                sensors.extend(_build_sensors_for_fixture(facility, zone, fixture))

    return FacilityTopology(
        facility=facility,
        zones=zones,
        fixtures=fixtures,
        sensors=sensors,
    )


def available_presets() -> list[str]:
    """Return supported preset names."""

    return sorted(PRESETS.keys())


def _build_sensors_for_fixture(
    facility: FacilityDefinition,
    zone: ZoneDefinition,
    fixture: FixtureDefinition,
) -> list[SensorDefinition]:
    sensors: list[SensorDefinition] = [
        SensorDefinition(
            sensor_id=f"{fixture.fixture_id}-flow",
            fixture_id=fixture.fixture_id,
            zone_id=zone.zone_id,
            facility_id=facility.facility_id,
            sensor_type=SensorType.FLOW_METER.value,
            unit=Unit.L_PER_MIN.value,
        ),
        SensorDefinition(
            sensor_id=f"{fixture.fixture_id}-diag",
            fixture_id=fixture.fixture_id,
            zone_id=zone.zone_id,
            facility_id=facility.facility_id,
            sensor_type=SensorType.DIAGNOSTIC.value,
            unit=Unit.STATUS_CODE.value,
        ),
    ]

    if fixture.fixture_type in {"flush_valve", "urinal"}:
        sensors.append(
            SensorDefinition(
                sensor_id=f"{fixture.fixture_id}-flush",
                fixture_id=fixture.fixture_id,
                zone_id=zone.zone_id,
                facility_id=facility.facility_id,
                sensor_type=SensorType.FLUSH_COUNTER.value,
                unit=Unit.COUNT.value,
            )
        )

    if fixture.fixture_type == "water_line":
        sensors.append(
            SensorDefinition(
                sensor_id=f"{fixture.fixture_id}-occupancy",
                fixture_id=fixture.fixture_id,
                zone_id=zone.zone_id,
                facility_id=facility.facility_id,
                sensor_type=SensorType.OCCUPANCY_PIR.value,
                unit=Unit.PERSONS.value,
            )
        )

    return sensors


def _slugify(value: str) -> str:
    return "-".join(value.lower().replace("/", " ").split())


def _installation_age(zone_index: int, fixture_number: int) -> int:
    return 1 + ((zone_index + fixture_number) % 9)


def _expected_lifetime_cycles(fixture_type: str) -> int:
    lifetimes = {
        "faucet": 250_000,
        "flush_valve": 500_000,
        "urinal": 400_000,
        "water_line": 750_000,
    }
    return lifetimes[fixture_type]
