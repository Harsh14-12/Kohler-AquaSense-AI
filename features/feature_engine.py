"""Fixture-level feature engineering for AquaSense telemetry."""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime
from math import sqrt
from statistics import mean, median
from typing import Iterable, Optional

from schemas.telemetry import (
    DiagnosticStatus,
    QualityFlag,
    SensorReading,
    SensorType,
)

from .schemas import FeatureVector


class FeatureEngine:
    """Convert raw SensorReading objects into deterministic FeatureVectors.

    State is maintained at fixture level because flow, occupancy, flush,
    and diagnostic sensors belonging to a fixture must be interpreted
    together.
    """

    def __init__(
        self,
        window_size: int = 12,
        minimum_baseline_history: int = 3,
        time_bucket_minutes: int = 60,
        minimum_dispersion: float = 0.05,
    ) -> None:
        if window_size < 2:
            raise ValueError("window_size must be at least 2")

        if minimum_baseline_history < 1:
            raise ValueError(
                "minimum_baseline_history must be positive"
            )

        if time_bucket_minutes <= 0:
            raise ValueError(
                "time_bucket_minutes must be positive"
            )

        if minimum_dispersion <= 0:
            raise ValueError(
                "minimum_dispersion must be positive"
            )

        self.window_size = window_size
        self.minimum_baseline_history = minimum_baseline_history
        self.time_bucket_minutes = time_bucket_minutes
        self.minimum_dispersion = minimum_dispersion

        self._history: dict[str, deque[SensorReading]] = defaultdict(
            lambda: deque(maxlen=self.window_size * 4)
        )

    @staticmethod
    def _fixture_key(reading: SensorReading) -> str:
        return (
            f"{reading.facility_id}:"
            f"{reading.zone_id}:"
            f"{reading.fixture_id}"
        )

    @staticmethod
    def _safe_mean(values: list[float]) -> float:
        return mean(values) if values else 0.0

    @staticmethod
    def _variance(values: list[float]) -> float:
        if len(values) < 2:
            return 0.0

        average = mean(values)

        return sum(
            (value - average) ** 2 for value in values
        ) / len(values)

    @staticmethod
    def _mad(values: list[float]) -> float:
        if not values:
            return 0.0

        middle = median(values)

        deviations = [
            abs(value - middle)
            for value in values
        ]

        return median(deviations)

    @staticmethod
    def _minutes_between(
        earlier: Optional[datetime],
        later: datetime,
    ) -> float:
        if earlier is None:
            return 0.0

        seconds = (
            later - earlier
        ).total_seconds()

        return max(0.0, seconds / 60.0)

    @staticmethod
    def _diagnostic_health(
        readings: list[SensorReading],
    ) -> float:
        if not readings:
            return 1.0

        latest = max(
            readings,
            key=lambda item: item.timestamp,
        )

        health_map = {
            DiagnosticStatus.OK.value: 1.0,
            DiagnosticStatus.BATTERY_LOW.value: 0.75,
            DiagnosticStatus.DEGRADED.value: 0.50,
            DiagnosticStatus.OFFLINE.value: 0.0,
        }

        health = health_map.get(
            latest.diagnostic_status,
            0.5,
        )

        if latest.quality_flag == QualityFlag.STALE.value:
            health = min(health, 0.25)

        if latest.quality_flag == QualityFlag.OUT_OF_RANGE.value:
            health = min(health, 0.25)

        return health

    @staticmethod
    def _latest(
        readings: list[SensorReading],
        sensor_type: SensorType,
    ) -> Optional[SensorReading]:
        candidates = [
            item
            for item in readings
            if item.sensor_type == sensor_type.value
        ]

        if not candidates:
            return None

        return max(
            candidates,
            key=lambda item: item.timestamp,
        )

    def _baseline(
        self,
        reading: SensorReading,
        flow_history: list[SensorReading],
    ) -> tuple[float, float, float]:
        """Calculate a historical, time-aware flow baseline.

        Only observations strictly earlier than the current reading are
        eligible, preventing future-data leakage.
        """

        previous = [
            item
            for item in flow_history
            if item.timestamp < reading.timestamp
            and item.quality_flag != QualityFlag.OUT_OF_RANGE.value
        ]

        if not previous:
            return 0.0, 0.0, 0.0

        current_minutes = (
            reading.timestamp.hour * 60
            + reading.timestamp.minute
        )

        current_bucket = (
            current_minutes // self.time_bucket_minutes
        )

        same_bucket = [
            item
            for item in previous
            if (
                (
                    item.timestamp.hour * 60
                    + item.timestamp.minute
                )
                // self.time_bucket_minutes
            )
            == current_bucket
        ]

        if len(same_bucket) >= self.minimum_baseline_history:
            candidates = same_bucket
        else:
            candidates = previous

        values = [
            item.value
            for item in candidates
        ]

        baseline = median(values)

        mad = self._mad(values)

        robust_sigma = 1.4826 * mad

        if robust_sigma < self.minimum_dispersion:
            standard_deviation = sqrt(
                self._variance(values)
            )

            robust_sigma = max(
                standard_deviation,
                self.minimum_dispersion,
            )

        deviation = reading.value - baseline

        sigma = deviation / robust_sigma

        return (
            float(baseline),
            float(deviation),
            float(sigma),
        )

    @staticmethod
    def _flush_events(
        flush_readings: list[SensorReading],
    ) -> list[SensorReading]:
        """Return flush readings where cumulative counter increased."""

        ordered = sorted(
            flush_readings,
            key=lambda item: item.timestamp,
        )

        events: list[SensorReading] = []

        for previous, current in zip(
            ordered,
            ordered[1:],
        ):
            if current.value > previous.value:
                events.append(current)

        return events

    def _fixture_history(
        self,
        reading: SensorReading,
    ) -> list[SensorReading]:
        return list(
            self._history[
                self._fixture_key(reading)
            ]
        )

    def update(
        self,
        reading: SensorReading,
    ) -> FeatureVector:
        """Add one reading and calculate the current feature vector."""

        key = self._fixture_key(reading)

        history = self._history[key]

        previous_same_sensor = None

        for item in reversed(history):
            if item.sensor_id == reading.sensor_id:
                previous_same_sensor = item
                break

        history.append(reading)

        fixture_readings = [
            item
            for item in history
            if item.timestamp <= reading.timestamp
        ]

        flow_readings = [
            item
            for item in fixture_readings
            if item.sensor_type == SensorType.FLOW_METER.value
        ]

        occupancy_readings = [
            item
            for item in fixture_readings
            if item.sensor_type
            == SensorType.OCCUPANCY_PIR.value
        ]

        flush_readings = [
            item
            for item in fixture_readings
            if item.sensor_type
            == SensorType.FLUSH_COUNTER.value
        ]

        diagnostic_readings = [
            item
            for item in fixture_readings
            if item.sensor_type
            == SensorType.DIAGNOSTIC.value
        ]

        latest_flow = self._latest(
            fixture_readings,
            SensorType.FLOW_METER,
        )

        latest_occupancy = self._latest(
            fixture_readings,
            SensorType.OCCUPANCY_PIR,
        )

        latest_flush = self._latest(
            fixture_readings,
            SensorType.FLUSH_COUNTER,
        )

        current_flow = (
            latest_flow.value
            if latest_flow is not None
            else 0.0
        )

        occupancy = (
            latest_occupancy.value
            if latest_occupancy is not None
            else 0.0
        )

        recent_flow = [
            item.value
            for item in flow_readings[
                -self.window_size :
            ]
        ]

        recent_occupancy = [
            item.value
            for item in occupancy_readings[
                -self.window_size :
            ]
        ]

        average_flow = self._safe_mean(
            recent_flow
        )

        flow_variance = self._variance(
            recent_flow
        )

        previous_flow = (
            flow_readings[-2].value
            if len(flow_readings) >= 2
            else current_flow
        )

        flow_change = (
            current_flow - previous_flow
        )

        occupancy_average = self._safe_mean(
            recent_occupancy
        )

        flush_events = self._flush_events(
            flush_readings
        )

        flush_count = (
            latest_flush.value
            if latest_flush is not None
            else 0.0
        )

        recent_flush_events = [
            event
            for event in flush_events
            if event.timestamp <= reading.timestamp
        ]

        flush_rate = float(
    sum(
        max(0.0, current.value - previous.value)
        for previous, current in zip(
            flush_readings[:-1],
            flush_readings[1:],
        )
        if current.timestamp <= reading.timestamp
        and self._minutes_between(
            current.timestamp,
            reading.timestamp,
        ) <= 60.0
    )
)

        usage_per_occupant = (
            flush_rate / occupancy_average
            if occupancy_average > 0
            else 0.0
        )

        last_flush_time = (
            recent_flush_events[-1].timestamp
            if recent_flush_events
            else None
        )

        time_since_last_flush = (
            self._minutes_between(
                last_flush_time,
                reading.timestamp,
            )
            if last_flush_time is not None
            else 0.0
        )

        last_usage_time = last_flush_time

        time_since_last_usage = (
            self._minutes_between(
                last_usage_time,
                reading.timestamp,
            )
            if last_usage_time is not None
            else 0.0
        )

        idle_flow_minutes = 0.0

        if (
            current_flow > 0.0
            and occupancy <= 0.0
            and previous_same_sensor is not None
        ):
            idle_flow_minutes = self._minutes_between(
                previous_same_sensor.timestamp,
                reading.timestamp,
            )

        baseline = 0.0
        baseline_deviation = 0.0
        baseline_sigma = 0.0

        if latest_flow is not None:
            (
                baseline,
                baseline_deviation,
                baseline_sigma,
            ) = self._baseline(
                latest_flow,
                flow_readings,
            )

        reading_gap_minutes = 0.0

        if previous_same_sensor is not None:
            reading_gap_minutes = self._minutes_between(
                previous_same_sensor.timestamp,
                reading.timestamp,
            )

        return FeatureVector(
            timestamp=reading.timestamp,
            facility_id=reading.facility_id,
            zone_id=reading.zone_id,
            fixture_id=reading.fixture_id,
            sensor_id=reading.sensor_id,
            current_flow_rate=current_flow,
            average_flow_rate=average_flow,
            flow_variance=flow_variance,
            flow_change=flow_change,
            occupancy=occupancy,
            occupancy_average=occupancy_average,
            flush_rate=flush_rate,
            flush_count=flush_count,
            usage_per_occupant=usage_per_occupant,
            idle_flow_minutes=idle_flow_minutes,
            time_since_last_flush=time_since_last_flush,
            time_since_last_usage=time_since_last_usage,
            baseline_flow=baseline,
            baseline_deviation=baseline_deviation,
            baseline_deviation_sigma=baseline_sigma,
            diagnostic_health=self._diagnostic_health(
                diagnostic_readings
            ),
            reading_gap_minutes=reading_gap_minutes,
        )

    def process(
        self,
        readings: Iterable[SensorReading],
    ) -> list[FeatureVector]:
        """Process telemetry chronologically."""

        ordered = sorted(
            readings,
            key=lambda item: item.timestamp,
        )

        return [
            self.update(reading)
            for reading in ordered
        ]