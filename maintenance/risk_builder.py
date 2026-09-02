from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

from detection.schemas import (
    AnomalyEvent,
    AnomalySeverity,
    AnomalyType,
)

from .schemas import MaintenanceRiskInput


class MaintenanceRiskBuilder:
    """
    Builds MaintenanceRiskInput from historical anomaly events.

    This component translates raw anomaly history into the
    interpretable signals required by MaintenanceRiskEngine.

    The builder is deterministic and contains no ML.
    """

    def __init__(
        self,
        recent_window_days: float = 7.0,
    ) -> None:
        if recent_window_days <= 0.0:
            raise ValueError(
                "recent_window_days must be greater than zero."
            )

        self.recent_window_days = recent_window_days

    # ------------------------------------------------------------------
    # Public builder
    # ------------------------------------------------------------------

    def build(
        self,
        fixture_id: str,
        events: Iterable[AnomalyEvent],
        reference_time: datetime | None = None,
        sensor_health: float = 1.0,
        days_since_last_maintenance: float = 0.0,
    ) -> MaintenanceRiskInput:
        """
        Build a MaintenanceRiskInput for one fixture.

        Only events belonging to fixture_id are considered.
        """

        if not 0.0 <= sensor_health <= 1.0:
            raise ValueError(
                "sensor_health must be between 0 and 1."
            )

        if days_since_last_maintenance < 0.0:
            raise ValueError(
                "days_since_last_maintenance "
                "cannot be negative."
            )

        event_list = [
            event
            for event in events
            if event.fixture_id == fixture_id
        ]

        if reference_time is None:
            reference_time = self._get_reference_time(
                event_list
            )

        recent_cutoff = (
            reference_time
            - timedelta(
                days=self.recent_window_days
            )
        )

        recent_events = [
            event
            for event in event_list
            if self._is_recent(
                event.timestamp,
                recent_cutoff,
            )
        ]

        high_severity_count = sum(
            1
            for event in event_list
            if event.severity
            in {
                AnomalySeverity.HIGH,
                AnomalySeverity.CRITICAL,
            }
        )

        critical_count = sum(
            1
            for event in event_list
            if event.severity
            == AnomalySeverity.CRITICAL
        )

        abnormal_flow_count = sum(
            1
            for event in event_list
            if event.anomaly_type
            == AnomalyType.ABNORMAL_FLOW
        )

        persistent_minutes = self._calculate_persistence(
            event_list
        )

        return MaintenanceRiskInput(
            fixture_id=fixture_id,
            anomaly_count=len(event_list),
            recent_anomaly_count=len(
                recent_events
            ),
            high_severity_anomaly_count=(
                high_severity_count
            ),
            critical_anomaly_count=(
                critical_count
            ),
            sensor_health=sensor_health,
            abnormal_flow_events=(
                abnormal_flow_count
            ),
            persistent_anomaly_minutes=(
                persistent_minutes
            ),
            days_since_last_maintenance=(
                days_since_last_maintenance
            ),
        )

    # ------------------------------------------------------------------
    # Reference time
    # ------------------------------------------------------------------

    def _get_reference_time(
        self,
        events: list[AnomalyEvent],
    ) -> datetime:
        """
        Use the latest anomaly timestamp as the default
        reference time.

        If there are no events, use the current UTC time.
        """

        if not events:
            return datetime.now(
                timezone.utc
            )

        return max(
            event.timestamp
            for event in events
        )

    # ------------------------------------------------------------------
    # Recent event detection
    # ------------------------------------------------------------------

    def _is_recent(
        self,
        timestamp: datetime,
        cutoff: datetime,
    ) -> bool:
        """
        Determine whether an event falls within the recent window.
        """

        return timestamp >= cutoff

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _calculate_persistence(
        self,
        events: list[AnomalyEvent],
    ) -> float:
        """
        Estimate persistent anomaly duration.

        The calculation looks for repeated anomaly events from the
        same fixture and sums the elapsed time between consecutive
        anomaly observations.

        A single event contributes zero persistence because there
        is insufficient evidence to establish duration.
        """

        if len(events) < 2:
            return 0.0

        ordered = sorted(
            events,
            key=lambda event: event.timestamp,
        )

        total_minutes = 0.0

        for previous, current in zip(
            ordered,
            ordered[1:],
        ):
            elapsed = (
                current.timestamp
                - previous.timestamp
            ).total_seconds() / 60.0

            # Only count positive elapsed intervals.
            if elapsed > 0.0:
                total_minutes += elapsed

        return total_minutes