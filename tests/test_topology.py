from simulator.facility_topology import available_presets, build_facility_topology


def test_expected_presets_exist():
    assert available_presets() == ["airport", "hospital", "university"]


def test_airport_creation():
    topology = build_facility_topology("airport")
    assert topology.facility.facility_type == "airport"
    assert len(topology.zones) == 6


def test_hospital_creation():
    topology = build_facility_topology("hospital")
    assert topology.facility.facility_type == "hospital"
    assert len(topology.zones) == 4


def test_university_creation():
    topology = build_facility_topology("university")
    assert topology.facility.facility_type == "university"
    assert len(topology.zones) == 4


def test_fixtures_and_sensors_are_linked():
    topology = build_facility_topology("airport")
    fixture_ids = {fixture.fixture_id for fixture in topology.fixtures}
    zone_ids = {zone.zone_id for zone in topology.zones}
    assert fixture_ids
    assert topology.sensors
    for sensor in topology.sensors:
        assert sensor.fixture_id in fixture_ids
        assert sensor.zone_id in zone_ids
        assert sensor.facility_id == topology.facility.facility_id
