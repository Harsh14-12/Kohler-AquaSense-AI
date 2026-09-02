"""Synthetic occupancy model tuned for facility-specific behavior."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class FacilityOccupancyProfile:
    nighttime: float
    morning_peak: float
    midday: float
    evening_peak: float
    late_evening: float
    weekend_factor: float
    overnight_baseline: float


DEFAULT_PROFILES: dict[str, FacilityOccupancyProfile] = {
    "airport": FacilityOccupancyProfile(0.10, 0.88, 0.65, 0.92, 0.42, 1.05, 0.08),
    "hospital": FacilityOccupancyProfile(0.22, 0.58, 0.62, 0.56, 0.40, 0.94, 0.20),
    "university": FacilityOccupancyProfile(0.02, 0.60, 0.92, 0.28, 0.05, 0.32, 0.00),
}


ZONE_TYPE_MULTIPLIERS: dict[str, float] = {
    "restroom_airside": 1.15,
    "restroom_emergency": 0.90,
    "restroom_outpatient": 1.00,
    "restroom_ward": 0.78,
    "restroom_public": 0.95,
    "restroom_academic": 1.00,
    "restroom_library": 0.78,
    "restroom_student_center": 1.12,
    "restroom_admin": 0.64,
}


class OccupancyModel:
    """Estimate zone occupancy based on time and facility context."""

    def __init__(
        self,
        profiles: dict[str, FacilityOccupancyProfile] | None = None,
        zone_multipliers: dict[str, float] | None = None,
    ) -> None:
        self._profiles = profiles or DEFAULT_PROFILES
        self._zone_multipliers = zone_multipliers or ZONE_TYPE_MULTIPLIERS

    def get_expected_occupancy(
        self,
        timestamp: datetime,
        facility_type: str,
        zone_type: str,
        zone_capacity: int = 20,
        rng: random.Random | None = None,
    ) -> int:
        """Return a realistic non-negative occupancy count."""

        if facility_type not in self._profiles:
            raise ValueError(f"Unknown facility type: {facility_type}")

        profile = self._profiles[facility_type]
        base_load = self._time_of_day_load(timestamp.hour, facility_type, profile)
        zone_factor = self._zone_multipliers.get(zone_type, 1.0)
        weekend_factor = profile.weekend_factor if timestamp.weekday() >= 5 else 1.0
        noise_rng = rng or random.Random(timestamp.toordinal() * 100 + timestamp.hour)
        noise = noise_rng.uniform(-0.08, 0.08)

        occupancy_ratio = max(
            profile.overnight_baseline,
            base_load * zone_factor * weekend_factor + noise,
        )
        if facility_type == "university" and 0 <= timestamp.hour < 5:
            occupancy_ratio = min(occupancy_ratio, 0.03)
        occupancy_ratio = max(0.0, min(1.15, occupancy_ratio))
        occupancy = int(zone_capacity * occupancy_ratio)
        return max(0, occupancy)

    @staticmethod
    def _time_of_day_load(
        hour: int,
        facility_type: str,
        profile: FacilityOccupancyProfile,
    ) -> float:
        if 0 <= hour < 5:
            return profile.nighttime
        if 5 <= hour < 10:
            if facility_type == "airport":
                return OccupancyModel._interpolate(profile.nighttime, profile.morning_peak, hour, 5, 9)
            return OccupancyModel._interpolate(profile.nighttime, profile.morning_peak, hour, 5, 9)
        if 10 <= hour < 15:
            return OccupancyModel._interpolate(profile.morning_peak, profile.midday, hour, 10, 14)
        if 15 <= hour < 20:
            if facility_type == "airport":
                return OccupancyModel._interpolate(profile.midday, profile.evening_peak, hour, 15, 19)
            return OccupancyModel._interpolate(profile.midday, profile.evening_peak, hour, 15, 19)
        return OccupancyModel._interpolate(profile.evening_peak, profile.late_evening, hour, 20, 23)

    @staticmethod
    def _interpolate(start: float, end: float, hour: int, range_start: int, range_end: int) -> float:
        if range_end == range_start:
            return end
        progress = (hour - range_start) / float(range_end - range_start)
        progress = max(0.0, min(1.0, progress))
        return start + (end - start) * progress
