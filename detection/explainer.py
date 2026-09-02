from __future__ import annotations

from typing import List

from .schemas import AnomalyEvent


def explain_anomaly(
    event: AnomalyEvent,
) -> str:
    """
    Return the primary human-readable explanation for an anomaly.
    """

    return event.explanation


def explain_with_evidence(
    event: AnomalyEvent,
) -> str:
    """
    Return a human-readable explanation including:

    - anomaly explanation
    - rule that triggered it
    - evidence identifier
    - observed values
    - expected values
    - configured thresholds
    - feature deltas
    """

    trace = event.explanation_trace

    parts: List[str] = []

    # --------------------------------------------------------------
    # Main explanation
    # --------------------------------------------------------------

    if event.explanation:
        parts.append(event.explanation)

    # --------------------------------------------------------------
    # Rule
    # --------------------------------------------------------------

    if trace.rule:
        parts.append(
            f"Rule: {trace.rule}."
        )

    # --------------------------------------------------------------
    # Evidence identifier
    # --------------------------------------------------------------

    evidence_map = {
        "continuous_leak": "continuous_flow_while_unoccupied",
        "abnormal_flow": "flow_above_expected_baseline",
        "ghost_flush": "flush_activity_without_occupancy",
        "sensor_dropout": "sensor_health_or_reading_gap",
        "occupancy_spike": "occupancy_above_expected_pattern",
    }

    anomaly_type = event.anomaly_type.value

    evidence = evidence_map.get(
        anomaly_type,
        anomaly_type,
    )

    parts.append(
        f"Evidence: {evidence}."
    )

    # --------------------------------------------------------------
    # Continuous leak: explicitly expose flow-rate evidence
    # --------------------------------------------------------------

    if anomaly_type == "continuous_leak":
        flow_value = trace.observations.get(
            "flow_rate_l_per_min"
        )

        if flow_value is None:
            flow_value = trace.observations.get(
                "flow"
            )

        if flow_value is None:
            flow_value = event.observed_value

        parts.append(
            f"flow_rate_l_per_min={flow_value}."
        )

    # --------------------------------------------------------------
    # Observations
    # --------------------------------------------------------------

    if trace.observations:
        observation_text = ", ".join(
            f"{key}={value}"
            for key, value in trace.observations.items()
        )

        parts.append(
            f"Observed: {observation_text}."
        )

    # --------------------------------------------------------------
    # Expected values
    # --------------------------------------------------------------

    if trace.expected:
        expected_text = ", ".join(
            f"{key}={value}"
            for key, value in trace.expected.items()
        )

        parts.append(
            f"Expected: {expected_text}."
        )

    # --------------------------------------------------------------
    # Thresholds
    # --------------------------------------------------------------

    if trace.thresholds:
        threshold_text = ", ".join(
            f"{key}={value}"
            for key, value in trace.thresholds.items()
        )

        parts.append(
            f"Thresholds: {threshold_text}."
        )

    # --------------------------------------------------------------
    # Feature deltas
    # --------------------------------------------------------------

    if trace.feature_deltas:
        delta_text = ", ".join(
            f"{key}={value}"
            for key, value in trace.feature_deltas.items()
        )

        parts.append(
            f"Feature deltas: {delta_text}."
        )

    return " ".join(parts)