from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Dict, List, Optional, Set, Tuple

from features.schemas import FeatureVector

from .schemas import (
    AnomalyEvent,
    AnomalySeverity,
    AnomalyStatus,
    AnomalyType,
)


@dataclass
class RuleConfig:
    """
    Configuration for AquaSense AI anomaly detection rules.

    These are prototype engineering thresholds.
    They are not KOHLER product specifications.
    """

    # Continuous leak
    leak_flow_threshold: float = 2.0
    leak_occupancy_threshold: float = 0.10
    leak_duration_minutes: float = 10.0

    # Abnormal flow
    abnormal_flow_sigma: float = 3.0

    # Ghost flush
    ghost_flush_rate: float = 3.0

    # Sensor dropout
    sensor_health_threshold: float = 0.5
    sensor_gap_minutes: float = 5.0

    # Occupancy spike
    occupancy_spike_sigma: float = 3.0


class RuleEngine:
    """
    Deterministic and explainable anomaly detection engine.

    Rules:
        1. Continuous leak
        2. Abnormal flow
        3. Ghost flush
        4. Sensor dropout
        5. Occupancy spike

    Lifecycle:
        - Ongoing anomalies are deduplicated.
        - Resolved anomalies are stored in history.
        - A recurrence gets a new event ID.
    """

    def __init__(
        self,
        config: Optional[RuleConfig] = None,
    ) -> None:

        self.config = config or RuleConfig()

        # Currently active anomaly lifecycles.
        self._active_anomalies: Dict[
            Tuple[str, str, str, AnomalyType],
            AnomalyEvent,
        ] = {}

        # Complete lifecycle history.
        #
        # This contains:
        #   - opened anomalies
        #   - updated active anomalies
        #   - resolved anomalies
        self._event_history: List[AnomalyEvent] = []

        # Start time for continuous suspicious flow.
        self._leak_start_times: Dict[
            Tuple[str, str, str],
            object,
        ] = {}

    # ==================================================================
    # MAIN EVALUATION
    # ==================================================================

    def evaluate(
        self,
        features: FeatureVector,
    ) -> List[AnomalyEvent]:
        """
        Evaluate all anomaly rules for one feature vector.
        """

        detected: List[AnomalyEvent] = []

        rules = [
            self._check_continuous_leak,
            self._check_abnormal_flow,
            self._check_ghost_flush,
            self._check_sensor_dropout,
            self._check_occupancy_spike,
        ]

        for rule in rules:

            event = rule(features)

            if event is None:
                continue

            lifecycle_key = self._lifecycle_key(
                features,
                event.anomaly_type,
            )

            existing = self._active_anomalies.get(
                lifecycle_key
            )

            # ----------------------------------------------------------
            # Existing active anomaly
            # ----------------------------------------------------------

            if existing is not None:

                updated_event = existing.copy(
                    update={
                        "timestamp": event.timestamp,
                        "severity": event.severity,
                        "confidence": event.confidence,
                        "status": AnomalyStatus.OPEN,
                        "triggered_rules": event.triggered_rules,
                        "triggering_features": (
                            event.triggering_features
                        ),
                        "observed_value": (
                            event.observed_value
                        ),
                        "expected_value": (
                            event.expected_value
                        ),
                        "explanation": event.explanation,
                        "explanation_trace": (
                            event.explanation_trace
                        ),
                    }
                )

                self._active_anomalies[
                    lifecycle_key
                ] = updated_event

                detected.append(updated_event)

            # ----------------------------------------------------------
            # New anomaly
            # ----------------------------------------------------------

            else:

                self._active_anomalies[
                    lifecycle_key
                ] = event

                detected.append(event)

                self._add_to_history(event)

        # --------------------------------------------------------------
        # Resolve missing anomalies.
        # --------------------------------------------------------------

        detected_keys = {
            self._lifecycle_key(
                features,
                event.anomaly_type,
            )
            for event in detected
        }

        resolved_events = (
            self._resolve_missing_anomalies(
                features,
                detected_keys,
            )
        )

        detected.extend(resolved_events)

        return detected

    # ==================================================================
    # EVENT HISTORY
    # ==================================================================

    def _add_to_history(
        self,
        event: AnomalyEvent,
    ) -> None:
        """
        Add a new lifecycle event to history.
        """

        self._event_history.append(event)

    def get_event_history(
        self,
    ) -> List[AnomalyEvent]:
        """
        Return the complete anomaly lifecycle history.

        A copy of the list is returned so callers cannot accidentally
        modify the engine's internal history.
        """

        return list(self._event_history)

    def get_active_anomalies(self) -> List[AnomalyEvent]:
        """
        Return all currently active anomaly events.

        A copy of the list is returned so callers cannot directly
        modify the engine's internal active-anomaly registry.
        """

        return list(self._active_anomalies.values())

    # ==================================================================
    # PUBLIC INDIVIDUAL RULE METHODS
    # ==================================================================

    def evaluate_leak(
        self,
        features: FeatureVector,
    ) -> Optional[AnomalyEvent]:
        """
        Evaluate only the continuous leak rule.
        """

        return self._check_continuous_leak(features)

    def evaluate_abnormal_flow(
        self,
        features: FeatureVector,
    ) -> Optional[AnomalyEvent]:
        """
        Evaluate only the abnormal flow rule.
        """

        return self._check_abnormal_flow(features)

    def evaluate_ghost_flush(
        self,
        features: FeatureVector,
    ) -> Optional[AnomalyEvent]:
        """
        Evaluate only the ghost flush rule.
        """

        return self._check_ghost_flush(features)

    def evaluate_sensor_dropout(
        self,
        features: FeatureVector,
    ) -> Optional[AnomalyEvent]:
        """
        Evaluate only the sensor dropout rule.
        """

        return self._check_sensor_dropout(features)

    def evaluate_occupancy_spike(
        self,
        features: FeatureVector,
    ) -> Optional[AnomalyEvent]:
        """
        Evaluate only the occupancy spike rule.
        """

        return self._check_occupancy_spike(features)

    # ==================================================================
    # LIFECYCLE HELPERS
    # ==================================================================

    @staticmethod
    def _lifecycle_key(
        features: FeatureVector,
        anomaly_type: AnomalyType,
    ) -> Tuple[str, str, str, AnomalyType]:
        """
        Identity of an active anomaly lifecycle.

        Timestamp is excluded so ongoing anomalies can be
        deduplicated.
        """

        return (
            features.facility_id,
            features.zone_id,
            features.fixture_id,
            anomaly_type,
        )

    def _event_id(
        self,
        features: FeatureVector,
        anomaly_type: AnomalyType,
    ) -> str:
        """
        Generate a unique ID for a new anomaly occurrence.

        Timestamp ensures that a later recurrence receives a
        different lifecycle ID.
        """

        timestamp_key = features.timestamp.strftime(
            "%Y%m%d%H%M%S"
        )

        return (
            f"{features.facility_id}-"
            f"{features.zone_id}-"
            f"{features.fixture_id}-"
            f"{anomaly_type.value}-"
            f"{timestamp_key}"
        )

    def _resolve_missing_anomalies(
        self,
        features: FeatureVector,
        detected_keys: Set[
            Tuple[str, str, str, AnomalyType]
        ],
    ) -> List[AnomalyEvent]:
        """
        Resolve active anomalies that disappeared.
        """

        resolved: List[AnomalyEvent] = []

        for lifecycle_key, event in list(
            self._active_anomalies.items()
        ):

            (
                facility_id,
                zone_id,
                fixture_id,
                anomaly_type,
            ) = lifecycle_key

            # Only resolve anomalies belonging to the current
            # fixture.
            if (
                facility_id != features.facility_id
                or zone_id != features.zone_id
                or fixture_id != features.fixture_id
            ):
                continue

            # Still active.
            if lifecycle_key in detected_keys:
                continue

            # ----------------------------------------------------------
            # Resolve the anomaly.
            # ----------------------------------------------------------

            resolved_event = event.copy(
                update={
                    "timestamp": features.timestamp,
                    "status": AnomalyStatus.RESOLVED,
                }
            )

            resolved.append(resolved_event)

            # Store the resolved lifecycle in history.
            self._event_history.append(
                resolved_event
            )

            # Remove from active registry.
            del self._active_anomalies[
                lifecycle_key
            ]

        return resolved

    # ==================================================================
    # RULE 1 — CONTINUOUS LEAK
    # ==================================================================

    def _check_continuous_leak(
        self,
        features: FeatureVector,
    ) -> Optional[AnomalyEvent]:
        """
        Detect sustained water flow while the fixture is effectively
        unoccupied.
        """

        key = (
            features.facility_id,
            features.zone_id,
            features.fixture_id,
        )

        suspicious = (
            features.current_flow_rate
            >= self.config.leak_flow_threshold
            and features.occupancy
            <= self.config.leak_occupancy_threshold
        )

        # Condition disappeared.
        if not suspicious:

            self._leak_start_times.pop(
                key,
                None,
            )

            return None

        # Start tracking.
        if key not in self._leak_start_times:

            self._leak_start_times[key] = (
                features.timestamp
            )

        start_time = self._leak_start_times[key]

        duration_minutes = (
            features.timestamp - start_time
        ).total_seconds() / 60.0

        # Persistence requirement not reached.
        if (
            duration_minutes
            < self.config.leak_duration_minutes
        ):
            return None

        # --------------------------------------------------------------
        # Confidence
        # --------------------------------------------------------------

        confidence = min(
            1.0,
            0.70
            + min(
                0.30,
                duration_minutes
                / max(
                    self.config.leak_duration_minutes * 10.0,
                    1.0,
                ),
            ),
        )

        # --------------------------------------------------------------
        # Severity
        # --------------------------------------------------------------

        severity = self._severity_from_duration(
            duration_minutes
        )

        # --------------------------------------------------------------
        # Explanation
        # --------------------------------------------------------------

        explanation = (
            "Continuous leak suspected: sustained water flow "
            "was detected while the fixture was unoccupied."
        )

        # --------------------------------------------------------------
        # Evidence trace
        # --------------------------------------------------------------

        trace = {
            "rule": "continuous_leak",

            "evidence": [
                "continuous_flow_while_unoccupied"
            ],

            "observations": {
                "current_flow_rate": (
                    features.current_flow_rate
                ),
                "occupancy": features.occupancy,
                "duration_minutes": duration_minutes,
            },

            "expected": {
                "flow_rate": 0.0,
                "occupancy": 0.0,
            },

            "thresholds": {
                "leak_flow_threshold": (
                    self.config.leak_flow_threshold
                ),
                "leak_occupancy_threshold": (
                    self.config.leak_occupancy_threshold
                ),
                "leak_duration_minutes": (
                    self.config.leak_duration_minutes
                ),
            },

            "feature_deltas": {
                "flow_excess": max(
                    0.0,
                    features.current_flow_rate
                    - self.config.leak_flow_threshold,
                ),
                "occupancy_margin": (
                    self.config.leak_occupancy_threshold
                    - features.occupancy
                ),
            },
        }

        return self._build_event(
            features=features,
            anomaly_type=AnomalyType.CONTINUOUS_LEAK,
            severity=severity,
            confidence=confidence,
            triggered_rules=[
                "continuous_leak"
            ],
            triggering_features=[
                "current_flow_rate",
                "occupancy",
                "idle_flow_minutes",
            ],
            observed_value=features.current_flow_rate,
            expected_value=0.0,
            explanation=explanation,
            explanation_trace=trace,
        )

    # ==================================================================
    # RULE 2 — ABNORMAL FLOW
    # ==================================================================

    def _check_abnormal_flow(
        self,
        features: FeatureVector,
    ) -> Optional[AnomalyEvent]:

        if features.baseline_flow <= 0:
            return None

        if features.baseline_deviation_sigma <= 0:
            return None

        if (
            abs(features.baseline_deviation_sigma)
            < self.config.abnormal_flow_sigma
        ):
            return None

        confidence = min(
            1.0,
            0.50
            + abs(
                features.baseline_deviation_sigma
            )
            / 10.0,
        )

        severity = (
            AnomalySeverity.HIGH
            if abs(
                features.baseline_deviation_sigma
            ) >= 5.0
            else AnomalySeverity.MEDIUM
        )

        explanation = (
            "Abnormal flow detected: current flow is "
            "significantly different from the historical baseline."
        )

        trace = {
            "rule": "abnormal_flow",

            "evidence": [
                "flow_deviation_from_baseline"
            ],

            "observations": {
                "current_flow_rate": (
                    features.current_flow_rate
                ),
                "baseline_flow": (
                    features.baseline_flow
                ),
                "baseline_deviation": (
                    features.baseline_deviation
                ),
                "baseline_deviation_sigma": (
                    features.baseline_deviation_sigma
                ),
            },

            "expected": {
                "baseline_flow": (
                    features.baseline_flow
                ),
            },

            "thresholds": {
                "abnormal_flow_sigma": (
                    self.config.abnormal_flow_sigma
                ),
            },

            "feature_deltas": {
                "flow_delta": (
                    features.baseline_deviation
                ),
                "sigma_delta": (
                    abs(
                        features.baseline_deviation_sigma
                    )
                    - self.config.abnormal_flow_sigma
                ),
            },
        }

        return self._build_event(
            features=features,
            anomaly_type=AnomalyType.ABNORMAL_FLOW,
            severity=severity,
            confidence=confidence,
            triggered_rules=[
                "abnormal_flow"
            ],
            triggering_features=[
                "current_flow_rate",
                "baseline_flow",
                "baseline_deviation_sigma",
            ],
            observed_value=features.current_flow_rate,
            expected_value=features.baseline_flow,
            explanation=explanation,
            explanation_trace=trace,
        )

    # ==================================================================
    # RULE 3 — GHOST FLUSH
    # ==================================================================

    def _check_ghost_flush(
        self,
        features: FeatureVector,
    ) -> Optional[AnomalyEvent]:

        if features.occupancy > 0:
            return None

        if (
            features.flush_rate
            < self.config.ghost_flush_rate
        ):
            return None

        confidence = min(
            1.0,
            0.60
            + min(
                0.40,
                features.flush_rate
                / max(
                    self.config.ghost_flush_rate * 5.0,
                    1.0,
                ),
            ),
        )

        severity = (
            AnomalySeverity.HIGH
            if features.flush_rate
            >= self.config.ghost_flush_rate * 2
            else AnomalySeverity.MEDIUM
        )

        explanation = (
            "Ghost flush suspected: repeated flush activity "
            "was detected while the zone was unoccupied."
        )

        trace = {
            "rule": "ghost_flush",

            "evidence": [
                "repeated_flush_while_unoccupied"
            ],

            "observations": {
                "flush_rate": features.flush_rate,
                "occupancy": features.occupancy,
            },

            "expected": {
                "flush_rate": 0.0,
            },

            "thresholds": {
                "ghost_flush_rate": (
                    self.config.ghost_flush_rate
                ),
            },

            "feature_deltas": {
                "flush_rate_excess": max(
                    0.0,
                    features.flush_rate
                    - self.config.ghost_flush_rate,
                ),
            },
        }

        return self._build_event(
            features=features,
            anomaly_type=AnomalyType.GHOST_FLUSH,
            severity=severity,
            confidence=confidence,
            triggered_rules=[
                "ghost_flush"
            ],
            triggering_features=[
                "flush_rate",
                "occupancy",
            ],
            observed_value=features.flush_rate,
            expected_value=0.0,
            explanation=explanation,
            explanation_trace=trace,
        )

    # ==================================================================
    # RULE 4 — SENSOR DROPOUT
    # ==================================================================

    def _check_sensor_dropout(
        self,
        features: FeatureVector,
    ) -> Optional[AnomalyEvent]:

        health_failure = (
            features.diagnostic_health
            < self.config.sensor_health_threshold
        )

        # Strictly greater than the configured gap.
        #
        # Therefore a gap of exactly 5 minutes is still considered
        # acceptable when sensor_gap_minutes = 5.
        gap_failure = (
            features.reading_gap_minutes
            > self.config.sensor_gap_minutes
        )

        if not health_failure and not gap_failure:
            return None

        severity = (
            AnomalySeverity.HIGH
            if health_failure and gap_failure
            else AnomalySeverity.MEDIUM
        )

        explanation = (
            "Sensor dropout suspected: telemetry health or "
            "reading continuity is below the expected level."
        )

        trace = {
            "rule": "sensor_dropout",

            "evidence": [
                "sensor_health_or_reading_gap"
            ],

            "observations": {
                "diagnostic_health": (
                    features.diagnostic_health
                ),
                "reading_gap_minutes": (
                    features.reading_gap_minutes
                ),
            },

            "expected": {
                "diagnostic_health": 1.0,
                "reading_gap_minutes": 0.0,
            },

            "thresholds": {
                "sensor_health_threshold": (
                    self.config.sensor_health_threshold
                ),
                "sensor_gap_minutes": (
                    self.config.sensor_gap_minutes
                ),
            },

            "feature_deltas": {
                "health_deficit": max(
                    0.0,
                    self.config.sensor_health_threshold
                    - features.diagnostic_health,
                ),
                "gap_excess": max(
                    0.0,
                    features.reading_gap_minutes
                    - self.config.sensor_gap_minutes,
                ),
            },
        }

        triggering_features: List[str] = []

        if health_failure:
            triggering_features.append(
                "diagnostic_health"
            )

        if gap_failure:
            triggering_features.append(
                "reading_gap_minutes"
            )

        if gap_failure:
            observed_value = (
                features.reading_gap_minutes
            )
            expected_value = 0.0
        else:
            observed_value = (
                features.diagnostic_health
            )
            expected_value = 1.0

        return self._build_event(
            features=features,
            anomaly_type=AnomalyType.SENSOR_DROPOUT,
            severity=severity,
            confidence=0.90,
            triggered_rules=[
                "sensor_dropout"
            ],
            triggering_features=triggering_features,
            observed_value=observed_value,
            expected_value=expected_value,
            explanation=explanation,
            explanation_trace=trace,
        )

    # ==================================================================
    # RULE 5 — OCCUPANCY SPIKE
    # ==================================================================

    def _check_occupancy_spike(
        self,
        features: FeatureVector,
    ) -> Optional[AnomalyEvent]:

        if features.occupancy_average <= 0:
            return None

        deviation = (
            features.occupancy
            - features.occupancy_average
        )

        expected_sigma = max(
            sqrt(
                features.occupancy_average
            ),
            1.0,
        )

        sigma_score = (
            deviation
            / expected_sigma
        )

        if (
            sigma_score
            < self.config.occupancy_spike_sigma
        ):
            return None

        confidence = min(
            1.0,
            0.50
            + sigma_score / 10.0,
        )

        severity = (
            AnomalySeverity.HIGH
            if sigma_score >= 5.0
            else AnomalySeverity.MEDIUM
        )

        explanation = (
            "Occupancy spike detected: current occupancy is "
            "significantly above the normal occupancy level."
        )

        trace = {
            "rule": "occupancy_spike",

            "evidence": [
                "occupancy_above_normal_baseline"
            ],

            "observations": {
                "occupancy": features.occupancy,
                "occupancy_average": (
                    features.occupancy_average
                ),
                "sigma_score": sigma_score,
            },

            "expected": {
                "occupancy": (
                    features.occupancy_average
                ),
            },

            "thresholds": {
                "occupancy_spike_sigma": (
                    self.config.occupancy_spike_sigma
                ),
            },

            "feature_deltas": {
                "occupancy_excess": deviation,
                "sigma_excess": (
                    sigma_score
                    - self.config.occupancy_spike_sigma
                ),
            },
        }

        return self._build_event(
            features=features,
            anomaly_type=AnomalyType.OCCUPANCY_SPIKE,
            severity=severity,
            confidence=confidence,
            triggered_rules=[
                "occupancy_spike"
            ],
            triggering_features=[
                "occupancy",
                "occupancy_average",
            ],
            observed_value=features.occupancy,
            expected_value=features.occupancy_average,
            explanation=explanation,
            explanation_trace=trace,
        )

    # ==================================================================
    # EVENT BUILDER
    # ==================================================================

    def _build_event(
        self,
        features: FeatureVector,
        anomaly_type: AnomalyType,
        severity: AnomalySeverity,
        confidence: float,
        triggered_rules: List[str],
        triggering_features: List[str],
        observed_value: float,
        expected_value: float,
        explanation: str,
        explanation_trace: dict,
    ) -> AnomalyEvent:
        """
        Build a new anomaly event.
        """

        return AnomalyEvent(
            event_id=self._event_id(
                features,
                anomaly_type,
            ),
            facility_id=features.facility_id,
            zone_id=features.zone_id,
            fixture_id=features.fixture_id,
            timestamp=features.timestamp,
            anomaly_type=anomaly_type,
            severity=severity,
            confidence=max(
                0.0,
                min(
                    1.0,
                    confidence,
                ),
            ),
            status=AnomalyStatus.OPEN,
            triggered_rules=triggered_rules,
            triggering_features=triggering_features,
            observed_value=observed_value,
            expected_value=expected_value,
            explanation=explanation,
            explanation_trace=explanation_trace,
        )

    # ==================================================================
    # SEVERITY
    # ==================================================================

    @staticmethod
    def _severity_from_duration(
        duration_minutes: float,
    ) -> AnomalySeverity:

        if duration_minutes >= 60:
            return AnomalySeverity.CRITICAL

        if duration_minutes >= 30:
            return AnomalySeverity.HIGH

        return AnomalySeverity.MEDIUM