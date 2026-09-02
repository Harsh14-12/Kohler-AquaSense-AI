from __future__ import annotations

from detection.schemas import AnomalyEvent
from ml.schemas import MLAnomalyResult

from .schemas import FusionDecision, FusionResult


class FusionEngine:
    """
    Combines deterministic rule-based detection with
    unsupervised ML anomaly detection.

    Design principle:

        Rules = explicit operational knowledge
        ML    = discovery of unusual patterns

    Explicit sensor issues take priority because an unreliable
    sensor can make statistical predictions misleading.
    """

    def combine(
        self,
        rule_event: AnomalyEvent | None,
        ml_result: MLAnomalyResult | None,
    ) -> FusionResult:
        """
        Combine rule and ML results into one operational decision.
        """

        rule_detected = rule_event is not None

        ml_detected = (
            ml_result is not None
            and ml_result.is_anomaly
        )

        rule_confidence = (
            rule_event.confidence
            if rule_event is not None
            else 0.0
        )

        ml_confidence = (
            ml_result.confidence
            if ml_result is not None
            else 0.0
        )

        # ----------------------------------------------------------
        # Sensor issue has highest priority
        # ----------------------------------------------------------

        if (
            rule_event is not None
            and rule_event.anomaly_type.value
            == "sensor_dropout"
        ):
            return FusionResult(
                decision=FusionDecision.SENSOR_ISSUE,
                rule_detected=True,
                ml_detected=ml_detected,
                rule_confidence=rule_confidence,
                ml_confidence=ml_confidence,
                combined_confidence=rule_confidence,
                reason=(
                    "A sensor reliability issue was detected. "
                    "The sensor issue takes priority because "
                    "unreliable telemetry can invalidate ML "
                    "interpretation."
                ),
                rule_anomaly_type=(
                    rule_event.anomaly_type.value
                ),
                ml_model=(
                    ml_result.model_name
                    if ml_result is not None
                    else None
                ),
            )

        # ----------------------------------------------------------
        # Both rule and ML detect anomaly
        # ----------------------------------------------------------

        if rule_detected and ml_detected:
            combined_confidence = min(
                1.0,
                0.6 * rule_confidence
                + 0.4 * ml_confidence,
            )

            return FusionResult(
                decision=FusionDecision.HIGH_CONFIDENCE_ANOMALY,
                rule_detected=True,
                ml_detected=True,
                rule_confidence=rule_confidence,
                ml_confidence=ml_confidence,
                combined_confidence=combined_confidence,
                reason=(
                    "The operational rule and the statistical "
                    "ML detector independently identified "
                    "anomalous behaviour."
                ),
                rule_anomaly_type=(
                    rule_event.anomaly_type.value
                ),
                ml_model=ml_result.model_name,
            )

        # ----------------------------------------------------------
        # Rule only
        # ----------------------------------------------------------

        if rule_detected:
            return FusionResult(
                decision=FusionDecision.RULE_ANOMALY,
                rule_detected=True,
                ml_detected=False,
                rule_confidence=rule_confidence,
                ml_confidence=0.0,
                combined_confidence=rule_confidence,
                reason=(
                    "An explicit operational rule detected "
                    "anomalous behaviour."
                ),
                rule_anomaly_type=(
                    rule_event.anomaly_type.value
                ),
                ml_model=None,
            )

        # ----------------------------------------------------------
        # ML only
        # ----------------------------------------------------------

        if ml_detected:
            return FusionResult(
                decision=FusionDecision.ML_ANOMALY,
                rule_detected=False,
                ml_detected=True,
                rule_confidence=0.0,
                ml_confidence=ml_confidence,
                combined_confidence=ml_confidence,
                reason=(
                    "The statistical detector identified a "
                    "multivariate operating pattern that differs "
                    "from learned normal behaviour."
                ),
                rule_anomaly_type=None,
                ml_model=ml_result.model_name,
            )

        # ----------------------------------------------------------
        # Normal
        # ----------------------------------------------------------

        return FusionResult(
            decision=FusionDecision.NORMAL,
            rule_detected=False,
            ml_detected=False,
            rule_confidence=0.0,
            ml_confidence=0.0,
            combined_confidence=0.0,
            reason=(
                "Neither the operational rules nor the "
                "statistical detector identified an anomaly."
            ),
            rule_anomaly_type=None,
            ml_model=(
                ml_result.model_name
                if ml_result is not None
                else None
            ),
        )