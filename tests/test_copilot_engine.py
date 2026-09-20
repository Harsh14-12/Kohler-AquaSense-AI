import logging

from copilot.context import AquaSenseCopilotContext
from copilot.engine import AquaSenseCopilotEngine
from copilot.schemas import CopilotEvidence


class FakeContextBuilder:
    def build_context(
        self,
        question,
        *,
        fixture_id=None,
        reading_limit=25,
    ):
        return [
            CopilotEvidence(
                source="maintenance_tickets",
                data={
                    "count": 1,
                    "tickets": [
                        {
                            "ticket_id": "TICKET-001",
                            "priority": "high",
                            "risk_score": 82.0,
                            "fixture_id": "FIXTURE-001",
                        }
                    ],
                },
            ),
            CopilotEvidence(
                source="recent_telemetry",
                data={
                    "count": 1,
                    "readings": [
                        {
                            "sensor_id": "SENSOR-001",
                            "value": 4.2,
                            "unit": "L/min",
                        }
                    ],
                },
            ),
        ]


class FailingLLM:
    def answer(self, question, evidence):
        raise RuntimeError("Simulated OpenAI failure")


def test_llm_failure_uses_deterministic_fallback(caplog):
    engine = AquaSenseCopilotEngine(
        FakeContextBuilder(),
        llm=FailingLLM(),
    )

    with caplog.at_level(logging.WARNING):
        result = engine.answer(
            "What maintenance issues are currently open?"
        )

    assert result.answer == (
        "AquaSense currently has 1 open maintenance "
        "ticket(s). 0 are critical priority and "
        "1 are high priority."
    )

    assert result.confidence == 0.95

    assert len(result.evidence) == 1
    assert result.evidence[0].source == "maintenance_tickets"

    assert "AquaSense LLM failed" in caplog.text


def test_engine_works_without_llm():
    engine = AquaSenseCopilotEngine(
        FakeContextBuilder(),
        llm=None,
    )

    result = engine.answer(
        "What maintenance issues are currently open?"
    )

    assert "1 open maintenance ticket" in result.answer
    assert result.confidence == 0.95