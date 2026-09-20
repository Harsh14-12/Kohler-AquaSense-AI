"""Schemas for the grounded AquaSense AI Copilot."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CopilotEvidence(BaseModel):
    """Structured evidence returned by an AquaSense Copilot tool."""

    source: str
    data: dict[str, Any] = Field(default_factory=dict)


class CopilotResponse(BaseModel):
    """Grounded response returned by the Copilot layer."""

    answer: str
    evidence: list[CopilotEvidence] = Field(default_factory=list)
    confidence: float | None = None