"""Grounded reasoning engine for the AquaSense AI Copilot."""

from __future__ import annotations

import logging

from .context import AquaSenseCopilotContext
from .schemas import CopilotEvidence, CopilotResponse


# ============================================================
# LOGGER
# ============================================================

logger = logging.getLogger(__name__)


# ============================================================
# COPILOT ENGINE
# ============================================================

class AquaSenseCopilotEngine:
    """
    Grounded reasoning layer for AquaSense AI.

    The engine:

    1. Retrieves structured evidence from AquaSense.
    2. Uses the LLM when available.
    3. Falls back safely to deterministic reasoning if the LLM
       is unavailable or fails.
    4. Never invents operational data.
    """

    def __init__(
        self,
        context_builder: AquaSenseCopilotContext,
        llm=None,
    ) -> None:
        """
        Initialize the Copilot engine.

        Parameters
        ----------
        context_builder:
            AquaSense context builder responsible for retrieving
            grounded operational evidence.

        llm:
            Optional LLM adapter.

            If None:
                deterministic reasoning is used.

            If supplied:
                the LLM is attempted first. If it fails,
                deterministic reasoning is used.
        """

        self.context_builder = context_builder
        self.llm = llm

    # ========================================================
    # PUBLIC API
    # ========================================================

    def answer(
        self,
        question: str,
        *,
        fixture_id: str | None = None,
        reading_limit: int = 25,
    ) -> CopilotResponse:
        """
        Answer an AquaSense operational question.

        Evidence is always retrieved before reasoning.

        If an LLM is available:
            LLM → response

        If the LLM fails:
            warning log → deterministic fallback

        If no LLM is configured:
            deterministic reasoning
        """

        # ----------------------------------------------------
        # Retrieve grounded evidence
        # ----------------------------------------------------

        evidence = self.context_builder.build_context(
            question,
            fixture_id=fixture_id,
            reading_limit=reading_limit,
        )

        # ----------------------------------------------------
        # Try LLM when available
        # ----------------------------------------------------

        if self.llm is not None:

            try:
                return self.llm.answer(
                    question,
                    evidence,
                )

            except Exception as exc:
                logger.warning(
                    "AquaSense LLM failed; using deterministic "
                    "fallback: %s",
                    exc,
                )

        # ----------------------------------------------------
        # Deterministic fallback
        # ----------------------------------------------------

        return self._deterministic_answer(
            question=question,
            evidence=evidence,
            fixture_id=fixture_id,
        )

    # ========================================================
    # DETERMINISTIC ROUTER
    # ========================================================

    def _deterministic_answer(
        self,
        *,
        question: str,
        evidence: list[CopilotEvidence],
        fixture_id: str | None,
    ) -> CopilotResponse:
        """
        Produce a deterministic answer from structured evidence.

        Routing priority:

        1. Maintenance / incidents
        2. Telemetry / readings
        3. Fixture-specific investigation
        4. General overview

        Maintenance questions are intentionally checked before
        fixture-specific questions.
        """

        context = {
            item.source: item.data
            for item in evidence
        }

        question_lower = question.lower().strip()

        # ----------------------------------------------------
        # Maintenance / incidents
        # ----------------------------------------------------

        if any(
            word in question_lower
            for word in (
                "maintenance",
                "ticket",
                "incident",
                "issue",
                "problem",
            )
        ):
            return self._maintenance_response(
                evidence,
                context,
            )

        # ----------------------------------------------------
        # Telemetry / readings
        # ----------------------------------------------------

        if any(
            word in question_lower
            for word in (
                "reading",
                "telemetry",
                "sensor",
                "flow",
                "occupancy",
            )
        ):
            return self._telemetry_response(
                evidence,
                context,
            )

        # ----------------------------------------------------
        # Fixture-specific investigation
        # ----------------------------------------------------

        if fixture_id is not None:
            return self._fixture_response(
                evidence,
                context,
                fixture_id,
            )

        # ----------------------------------------------------
        # General overview
        # ----------------------------------------------------

        return self._overview_response(
            evidence,
            context,
        )

    # ========================================================
    # MAINTENANCE RESPONSE
    # ========================================================

    def _maintenance_response(
        self,
        evidence: list[CopilotEvidence],
        context: dict,
    ) -> CopilotResponse:
        """
        Return deterministic maintenance information.
        """

        data = context.get(
            "maintenance_tickets",
            {},
        )

        tickets = data.get(
            "tickets",
            [],
        )

        count = data.get(
            "count",
            len(tickets),
        )

        # ----------------------------------------------------
        # No active tickets
        # ----------------------------------------------------

        if not tickets:

            answer = (
                "There are currently no open maintenance tickets "
                "in the AquaSense operational database."
            )

            confidence = 0.95

        # ----------------------------------------------------
        # Active tickets
        # ----------------------------------------------------

        else:

            critical = sum(
                1
                for ticket in tickets
                if ticket.get("priority") == "critical"
            )

            high = sum(
                1
                for ticket in tickets
                if ticket.get("priority") == "high"
            )

            answer = (
                f"AquaSense currently has {count} open maintenance "
                f"ticket(s). {critical} are critical priority and "
                f"{high} are high priority."
            )

            confidence = 0.95

        return CopilotResponse(
            answer=answer,
            evidence=[
                item
                for item in evidence
                if item.source == "maintenance_tickets"
            ],
            confidence=confidence,
        )

    # ========================================================
    # TELEMETRY RESPONSE
    # ========================================================

    def _telemetry_response(
        self,
        evidence: list[CopilotEvidence],
        context: dict,
    ) -> CopilotResponse:
        """
        Return deterministic telemetry information.
        """

        data = context.get(
            "recent_telemetry",
            {},
        )

        readings = data.get(
            "readings",
            [],
        )

        count = data.get(
            "count",
            len(readings),
        )

        # ----------------------------------------------------
        # No readings
        # ----------------------------------------------------

        if not readings:

            answer = (
                "No recent telemetry readings are currently "
                "available in the AquaSense database."
            )

            confidence = 0.90

        # ----------------------------------------------------
        # Readings available
        # ----------------------------------------------------

        else:

            latest = readings[0]

            answer = (
                f"AquaSense has {count} recent telemetry reading(s). "
                f"The latest available reading is from sensor "
                f"{latest.get('sensor_id')} with value "
                f"{latest.get('value')} {latest.get('unit')}."
            )

            confidence = 0.90

        return CopilotResponse(
            answer=answer,
            evidence=[
                item
                for item in evidence
                if item.source == "recent_telemetry"
            ],
            confidence=confidence,
        )

    # ========================================================
    # FIXTURE RESPONSE
    # ========================================================

    def _fixture_response(
        self,
        evidence: list[CopilotEvidence],
        context: dict,
        fixture_id: str,
    ) -> CopilotResponse:
        """
        Return deterministic fixture-specific information.
        """

        data = context.get(
            "fixture_telemetry",
            {},
        )

        readings = data.get(
            "readings",
            [],
        )

        count = data.get(
            "count",
            len(readings),
        )

        # ----------------------------------------------------
        # No fixture readings
        # ----------------------------------------------------

        if not readings:

            answer = (
                f"No persisted telemetry was found for fixture "
                f"{fixture_id}."
            )

            confidence = 0.90

        # ----------------------------------------------------
        # Fixture readings available
        # ----------------------------------------------------

        else:

            answer = (
                f"Fixture {fixture_id} has {count} persisted "
                f"telemetry reading(s) available for investigation."
            )

            confidence = 0.90

        return CopilotResponse(
            answer=answer,
            evidence=[
                item
                for item in evidence
                if item.source == "fixture_telemetry"
            ],
            confidence=confidence,
        )

    # ========================================================
    # OVERVIEW RESPONSE
    # ========================================================

    def _overview_response(
        self,
        evidence: list[CopilotEvidence],
        context: dict,
    ) -> CopilotResponse:
        """
        Return deterministic overall AquaSense status.
        """

        tickets = context.get(
            "maintenance_tickets",
            {},
        )

        telemetry = context.get(
            "recent_telemetry",
            {},
        )

        ticket_count = tickets.get(
            "count",
            0,
        )

        reading_count = telemetry.get(
            "count",
            0,
        )

        answer = (
            "AquaSense currently has "
            f"{ticket_count} open maintenance ticket(s) "
            f"and {reading_count} recent telemetry reading(s) "
            "available for operational analysis."
        )

        return CopilotResponse(
            answer=answer,
            evidence=evidence,
            confidence=0.85,
        )