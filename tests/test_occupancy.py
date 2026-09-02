from __future__ import annotations

import random
from datetime import datetime, timezone

from simulator.occupancy_model import OccupancyModel


def test_university_nighttime_lower_than_daytime():
    model = OccupancyModel()
    rng = random.Random(7)
    night = model.get_expected_occupancy(
        datetime(2026, 1, 7, 2, 0, tzinfo=timezone.utc),
        "university",
        "restroom_academic",
        30,
        rng,
    )
    day = model.get_expected_occupancy(
        datetime(2026, 1, 7, 13, 0, tzinfo=timezone.utc),
        "university",
        "restroom_academic",
        30,
        random.Random(7),
    )
    assert night < day


def test_hospital_retains_baseline_activity():
    model = OccupancyModel()
    occupancy = model.get_expected_occupancy(
        datetime(2026, 1, 7, 3, 0, tzinfo=timezone.utc),
        "hospital",
        "restroom_emergency",
        20,
        random.Random(3),
    )
    assert occupancy > 0


def test_airport_has_peak_periods():
    model = OccupancyModel()
    early_morning = model.get_expected_occupancy(
        datetime(2026, 1, 7, 6, 0, tzinfo=timezone.utc),
        "airport",
        "restroom_airside",
        40,
        random.Random(9),
    )
    late_night = model.get_expected_occupancy(
        datetime(2026, 1, 7, 1, 0, tzinfo=timezone.utc),
        "airport",
        "restroom_airside",
        40,
        random.Random(9),
    )
    assert early_morning > late_night


def test_values_are_non_negative():
    model = OccupancyModel()
    occupancy = model.get_expected_occupancy(
        datetime(2026, 1, 11, 23, 0, tzinfo=timezone.utc),
        "university",
        "restroom_library",
        20,
        random.Random(2),
    )
    assert occupancy >= 0
