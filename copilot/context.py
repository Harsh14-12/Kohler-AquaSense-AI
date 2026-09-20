"""Grounded context construction for the AquaSense AI Copilot."""

from __future__ import annotations

from typing import Any

from .schemas import CopilotEvidence
from .tools import AquaSenseCopilotTools


class AquaSenseCopilotContext:
    """
    Builds bounded, structured evidence for Copilot responses.

    This layer does not generate answers. It only retrieves and organizes
    facts from the existing AquaSense data-access tools.
    """

    def __init__(self, tools: AquaSenseCopilotTools) -> None:
        self.tools = tools

    def build_context(
        self,
        question: str,
        *,
        fixture_id: str | None = None,
        reading_limit: int = 25,
    ) -> list[CopilotEvidence]:
        """
        Build evidence relevant to a Copilot question.

        Parameters
        ----------
        question:
            User's natural-language question.

        fixture_id:
            Optional fixture to investigate specifically.

        reading_limit:
            Maximum recent telemetry records retrieved.
        """

        if not question.strip():
            raise ValueError("question must not be empty")

        if reading_limit < 1:
            raise ValueError("reading_limit must be at least 1")

        evidence: list[CopilotEvidence] = []

        # Current operational state
        evidence.append(
            self.tools.get_open_maintenance_tickets()
        )

        # Recent facility telemetry
        evidence.append(
            self.tools.get_recent_readings(
                limit=reading_limit
            )
        )

        # Fixture-specific investigation
        if fixture_id is not None:
            if not fixture_id.strip():
                raise ValueError("fixture_id must not be empty")

            evidence.append(
                self.tools.get_fixture_readings(
                    fixture_id=fixture_id,
                    limit=reading_limit,
                )
            )

        return evidence

    @staticmethod
    def to_prompt_context(
        evidence: list[CopilotEvidence],
    ) -> dict[str, Any]:
        """
        Convert structured evidence into a deterministic dictionary
        suitable for an LLM prompt.
        """

        return {
            item.source: item.data
            for item in evidence
        }