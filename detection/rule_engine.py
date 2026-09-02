"""Deterministic, explainable anomaly rules for AquaSense AI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from math import sqrt

from features.schemas import FeatureVector

from .schemas import (
    AnomalyEvent,
    AnomalySeverity,
    AnomalyStatus,
    AnomalyType,
    ExplanationTrace,
)


@dataclass
class RuleConfig:
    """Prototype thresholds for deterministic anomaly detection.

    These are engineering assumptions for the prototype, not KOHLER
    product specifications.
    """

    leak_flow_threshold: float = 0.50
    leak_occupancy_threshold: float = 0.10
    leak_duration_minutes: float = 10.0

    abnormal_flow_sigma: float = 3.0
    abnormal_flow_minimum: float = 0.75

    ghost_flush_occupancy_threshold: float = 0.10
    ghost_flush_rate_threshold: float = 2.0

    dropout_health_threshold: float = 0.25
    dropout_gap_minutes: float = 10.0

    occupancy_spike_sigma: float = 3.0
    occupancy_spike_minimum: float = 5.0

    medium_confidence: float = 0.70
    high_confidence: float = 0.85
    critical_confidence: float = 0.95


@dataclass
class LeakState:
    """State of a possible continuous leak."""

    started_at: Optional[datetime] = None
    last_timestamp: Optional[datetime] = None
    active: bool = False


class RuleEngine:
    """Stateful deterministic rule engine.

    Rules are deliberately transparent. Every generated event contains
    the rule that fired and structured evidence supporting the decision.
    """

    def __init__(
        self,
        config: Optional[RuleConfig] = None,
    ) -> None:
        self.config = config or RuleConfig()

        self._leak_states: dict[str, LeakState] = {}

    @staticmethod
    def _fixture_key(features: FeatureVector) -> str:
        return (
            f"{features.facility_id}:"
            f"{features.zone_id}:"
            f"{features.fixture_id}"
        )

    @staticmethod
    def _event_id(
        features: FeatureVector,
        anomaly_type: AnomalyType,
    ) -> str:
        timestamp = features.timestamp.strftime(
            "%Y%m%d%H%M%S"
        )

        return (
            f"{features.facility_id}-"
            f"{features.zone_id}-"
            f"{features.fixture_id}-"
            f"{anomaly_type.value}-"
            f"{timestamp}"
        )

    @staticmethod
    def _severity_from_confidence(
        confidence: float,
    ) -> AnomalySeverity:
        if confidence >= 0.95:
            return AnomalySeverity.CRITICAL

        if confidence >= 0.85:
            return AnomalySeverity.HIGH

        if confidence >= 0.70:
            return AnomalySeverity.MEDIUM

        return AnomalySeverity.LOW

    @staticmethod
    def _clamp_confidence(value: float) -> float:
        return max(0.0, min(1.0, value))

    def _make_event(
        self,
        features: FeatureVector,
        anomaly_type: AnomalyType,
        confidence: float,
        explanation: str,
        triggered_rule: str,
        triggering_features: list[str],
        observed_value: Optional[float],
        expected_value: Optional[float],
        observations: dict,
        expected: dict,
        thresholds: dict,
        feature_deltas: dict,
    ) -> AnomalyEvent:
        confidence = self._clamp_confidence(confidence)

        severity = self._severity_from_confidence(
            confidence
        )

        trace = ExplanationTrace(
            rule=triggered_rule,
            observations=observations,
            expected=expected,
            thresholds=thresholds,
            feature_deltas=feature_deltas,
        )

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
            confidence=confidence,
            status=AnomalyStatus.OPEN,
            triggered_rules=[triggered_rule],
            triggering_features=triggering_features,
            observed_value=observed_value,
            expected_value=expected_value,
            explanation=explanation,
            explanation_trace=trace,
        )

    def evaluate_leak(
        self,
        features: FeatureVector,
    ) -> Optional[AnomalyEvent]:
        """Detect sustained flow while the zone is unoccupied."""

        key = self._fixture_key(features)

        state = self._leak_states.setdefault(
            key,
            LeakState(),
        )

        flow_present = (
            features.current_flow_rate
            >= self.config.leak_flow_threshold
        )

        unoccupied = (
            features.occupancy
            <= self.config.leak_occupancy_threshold
        )

        if flow_present and unoccupied:
            if state.started_at is None:
                state.started_at = features.timestamp

            state.last_timestamp = features.timestamp

            duration = (
                features.timestamp - state.started_at
            ).total_seconds() / 60.0

            if duration >= self.config.leak_duration_minutes:
                state.active = True

                duration_factor = min(
                    1.0,
                    duration
                    / (
                        self.config.leak_duration_minutes
                        * 3.0
                    ),
                )

                flow_factor = min(
                    1.0,
                    features.current_flow_rate
                    / (
                        self.config.leak_flow_threshold
                        * 3.0
                    ),
                )

                confidence = (
                    0.70
                    + (0.15 * duration_factor)
                    + (0.15 * flow_factor)
                )

                return self._make_event(
                    features=features,
                    anomaly_type=AnomalyType.CONTINUOUS_LEAK,
                    confidence=confidence,
                    explanation=(
                        f"Continuous leak suspected: "
                        f"flow remained at "
                        f"{features.current_flow_rate:.2f} L/min "
                        f"while occupancy was "
                        f"{features.occupancy:.0f} for "
                        f"{duration:.1f} minutes, exceeding "
                        f"the {self.config.leak_duration_minutes:.1f}-"
                        f"minute persistence threshold."
                    ),
                    triggered_rule="continuous_flow_while_unoccupied",
                    triggering_features=[
                        "current_flow_rate",
                        "occupancy",
                        "idle_flow_minutes",
                    ],
                    observed_value=features.current_flow_rate,
                    expected_value=0.0,
                    observations={
                        "flow_rate_l_per_min": features.current_flow_rate,
                        "occupancy_persons": features.occupancy,
                        "duration_minutes": duration,
                    },
                    expected={
                        "flow_rate_l_per_min": 0.0,
                        "occupancy_persons": 0.0,
                    },
                    thresholds={
                        "flow_threshold_l_per_min":
                            self.config.leak_flow_threshold,
                        "occupancy_threshold":
                            self.config.leak_occupancy_threshold,
                        "duration_minutes":
                            self.config.leak_duration_minutes,
                    },
                    feature_deltas={
                        "flow_above_expected":
                            features.current_flow_rate,
                        "occupancy_difference":
                            features.occupancy,
                    },
                )

        else:
            state.started_at = None
            state.last_timestamp = None
            state.active = False

        return None

    def evaluate_abnormal_flow(
        self,
        features: FeatureVector,
    ) -> Optional[AnomalyEvent]:
        """Detect statistically abnormal flow."""

        if features.baseline_flow <= 0:
            return None

        if (
            features.current_flow_rate
            < self.config.abnormal_flow_minimum
        ):
            return None

        if (
            features.baseline_deviation_sigma
            < self.config.abnormal_flow_sigma
        ):
            return None

        sigma = features.baseline_deviation_sigma

        confidence = min(
            0.99,
            0.70 + (
                min(
                    1.0,
                    sigma
                    / (
                        self.config.abnormal_flow_sigma
                        * 2.0
                    ),
                )
                * 0.29
            ),
        )

        return self._make_event(
            features=features,
            anomaly_type=AnomalyType.ABNORMAL_FLOW,
            confidence=confidence,
            explanation=(
                f"Abnormal flow detected: current flow "
                f"of {features.current_flow_rate:.2f} L/min "
                f"is {features.baseline_deviation_sigma:.1f} "
                f"dispersion units above the historical "
                f"baseline of {features.baseline_flow:.2f} L/min."
            ),
            triggered_rule="flow_above_baseline_dispersion",
            triggering_features=[
                "current_flow_rate",
                "baseline_flow",
                "baseline_deviation_sigma",
            ],
            observed_value=features.current_flow_rate,
            expected_value=features.baseline_flow,
            observations={
                "current_flow_rate": features.current_flow_rate,
                "baseline_flow": features.baseline_flow,
                "sigma_deviation":
                    features.baseline_deviation_sigma,
            },
            expected={
                "flow_rate": features.baseline_flow,
            },
            thresholds={
                "sigma_threshold":
                    self.config.abnormal_flow_sigma,
                "minimum_flow":
                    self.config.abnormal_flow_minimum,
            },
            feature_deltas={
                "absolute_deviation":
                    features.baseline_deviation,
                "sigma_deviation":
                    features.baseline_deviation_sigma,
            },
        )

    def evaluate_ghost_flush(
        self,
        features: FeatureVector,
    ) -> Optional[AnomalyEvent]:
        """Detect unusually frequent flushing with no occupancy."""

        if (
            features.occupancy
            > self.config.ghost_flush_occupancy_threshold
        ):
            return None

        if (
            features.flush_rate
            < self.config.ghost_flush_rate_threshold
        ):
            return None

        confidence = min(
            0.98,
            0.72
            + min(
                0.26,
                (
                    features.flush_rate
                    / max(
                        1.0,
                        self.config.ghost_flush_rate_threshold,
                    )
                )
                * 0.08,
            ),
        )

        return self._make_event(
            features=features,
            anomaly_type=AnomalyType.GHOST_FLUSH,
            confidence=confidence,
            explanation=(
                f"Ghost flush suspected: "
                f"{features.flush_rate:.0f} flush events "
                f"were observed within the recent hour "
                f"while occupancy was "
                f"{features.occupancy:.0f}."
            ),
            triggered_rule="flush_activity_without_occupancy",
            triggering_features=[
                "flush_rate",
                "occupancy",
            ],
            observed_value=features.flush_rate,
            expected_value=0.0,
            observations={
                "flushes_last_hour":
                    features.flush_rate,
                "occupancy":
                    features.occupancy,
            },
            expected={
                "flushes_last_hour": 0.0,
                "occupancy": 0.0,
            },
            thresholds={
                "flush_rate_threshold":
                    self.config.ghost_flush_rate_threshold,
                "occupancy_threshold":
                    self.config.ghost_flush_occupancy_threshold,
            },
            feature_deltas={
                "unexpected_flushes":
                    features.flush_rate,
            },
        )

    def evaluate_sensor_dropout(
        self,
        features: FeatureVector,
    ) -> Optional[AnomalyEvent]:
        """Detect stale/offline/poor-quality telemetry."""

        if (
            features.diagnostic_health
            > self.config.dropout_health_threshold
            and features.reading_gap_minutes
            < self.config.dropout_gap_minutes
        ):
            return None

        poor_health = (
            features.diagnostic_health
            <= self.config.dropout_health_threshold
        )

        long_gap = (
            features.reading_gap_minutes
            >= self.config.dropout_gap_minutes
        )

        confidence = 0.70

        if poor_health:
            confidence += 0.15

        if long_gap:
            confidence += 0.15

        reason = []

        if poor_health:
            reason.append(
                f"diagnostic health is "
                f"{features.diagnostic_health:.2f}"
            )

        if long_gap:
            reason.append(
                f"reading gap is "
                f"{features.reading_gap_minutes:.1f} minutes"
            )

        return self._make_event(
            features=features,
            anomaly_type=AnomalyType.SENSOR_DROPOUT,
            confidence=confidence,
            explanation=(
                "Sensor/data-quality issue detected because "
                + " and ".join(reason)
                + "."
            ),
            triggered_rule="sensor_health_or_reading_gap",
            triggering_features=[
                "diagnostic_health",
                "reading_gap_minutes",
            ],
            observed_value=features.diagnostic_health,
            expected_value=1.0,
            observations={
                "diagnostic_health":
                    features.diagnostic_health,
                "reading_gap_minutes":
                    features.reading_gap_minutes,
            },
            expected={
                "diagnostic_health": 1.0,
                "reading_gap_minutes": 0.0,
            },
            thresholds={
                "health_threshold":
                    self.config.dropout_health_threshold,
                "gap_minutes":
                    self.config.dropout_gap_minutes,
            },
            feature_deltas={
                "health_difference":
                    1.0 - features.diagnostic_health,
                "gap_minutes":
                    features.reading_gap_minutes,
            },
        )

    def evaluate_occupancy_spike(
        self,
        features: FeatureVector,
    ) -> Optional[AnomalyEvent]:
        """Detect unusually high occupancy compared with its baseline."""

        if features.occupancy_average <= 0:
            return None

        deviation = (
            features.occupancy
            - features.occupancy_average
        )

        if (
            features.occupancy
            < self.config.occupancy_spike_minimum
        ):
            return None

        if (
            features.occupancy_average > 0
            and deviation
            < self.config.occupancy_spike_sigma
            * max(
                1.0,
                sqrt(features.occupancy_average),
            )
        ):
            return None

        confidence = min(
            0.98,
            0.70
            + min(
                0.28,
                deviation / max(
                    1.0,
                    features.occupancy_average * 2.0,
                ),
            ),
        )

        return self._make_event(
            features=features,
            anomaly_type=AnomalyType.OCCUPANCY_SPIKE,
            confidence=confidence,
            explanation=(
                f"Occupancy spike detected: "
                f"current occupancy of "
                f"{features.occupancy:.0f} is substantially "
                f"above the recent average of "
                f"{features.occupancy_average:.1f}."
            ),
            triggered_rule="occupancy_above_recent_baseline",
            triggering_features=[
                "occupancy",
                "occupancy_average",
            ],
            observed_value=features.occupancy,
            expected_value=features.occupancy_average,
            observations={
                "occupancy":
                    features.occupancy,
                "occupancy_average":
                    features.occupancy_average,
            },
            expected={
                "occupancy":
                    features.occupancy_average,
            },
            thresholds={
                "minimum_occupancy":
                    self.config.occupancy_spike_minimum,
                "sigma_threshold":
                    self.config.occupancy_spike_sigma,
            },
            feature_deltas={
                "occupancy_difference":
                    deviation,
            },
        )

    def evaluate(
        self,
        features: FeatureVector,
    ) -> list[AnomalyEvent]:
        """Run every deterministic rule against one feature vector."""

        events: list[AnomalyEvent] = []

        evaluators = (
            self.evaluate_leak,
            self.evaluate_abnormal_flow,
            self.evaluate_ghost_flush,
            self.evaluate_sensor_dropout,
            self.evaluate_occupancy_spike,
        )

        for evaluator in evaluators:
            event = evaluator(features)

            if event is not None:
                events.append(event)

        return events