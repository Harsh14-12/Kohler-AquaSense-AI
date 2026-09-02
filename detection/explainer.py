"""Human-readable explanation utilities for anomaly events."""

from __future__ import annotations

from .schemas import AnomalyEvent


def explain_anomaly(event: AnomalyEvent) -> str:
    """Return the deterministic explanation generated for an event."""

    return event.explanation


def explain_with_evidence(event: AnomalyEvent) -> str:
    """Return explanation plus the structured evidence used by the rule."""

    trace = event.explanation_trace

    observations = ", ".join(
        f"{key}={value}"
        for key, value in trace.observations.items()
    )

    expected = ", ".join(
        f"{key}={value}"
        for key, value in trace.expected.items()
    )

    thresholds = ", ".join(
        f"{key}={value}"
        for key, value in trace.thresholds.items()
    )

    return (
        f"{event.explanation} "
        f"Rule: {trace.rule}. "
        f"Observed: {observations}. "
        f"Expected: {expected}. "
        f"Thresholds: {thresholds}."
    )