from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from copilot.llm import AquaSenseLLM
from copilot.schemas import CopilotEvidence


def make_evidence():
    return [
        CopilotEvidence(
            source="maintenance_tickets",
            data={
                "count": 1,
                "tickets": [
                    {
                        "ticket_id": "TICKET-001",
                        "fixture_id": "FIXTURE-001",
                        "priority": "high",
                        "risk_score": 82.0,
                        "anomaly_type": "continuous_leak",
                        "status": "open",
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
                        "fixture_id": "FIXTURE-001",
                        "timestamp": datetime.now(
                            timezone.utc
                        ).isoformat(),
                        "value": 4.2,
                        "unit": "L/min",
                    }
                ],
            },
        ),
    ]


def test_build_context_returns_json():
    evidence = make_evidence()

    context = AquaSenseLLM._build_context(evidence)

    assert isinstance(context, str)
    assert "maintenance_tickets" in context
    assert "recent_telemetry" in context
    assert "TICKET-001" in context
    assert "FIXTURE-001" in context


def test_build_context_contains_actual_values():
    evidence = make_evidence()

    context = AquaSenseLLM._build_context(evidence)

    assert "82.0" in context
    assert "continuous_leak" in context
    assert "4.2" in context
    assert "L/min" in context


def test_confidence_with_no_evidence():
    confidence = AquaSenseLLM._estimate_confidence([])

    assert confidence == 0.0


def test_confidence_with_empty_evidence():
    evidence = [
        CopilotEvidence(
            source="maintenance_tickets",
            data={},
        )
    ]

    confidence = AquaSenseLLM._estimate_confidence(
        evidence
    )

    assert confidence == 0.50


def test_confidence_with_one_populated_source():
    evidence = [
        CopilotEvidence(
            source="maintenance_tickets",
            data={
                "count": 1,
            },
        )
    ]

    confidence = AquaSenseLLM._estimate_confidence(
        evidence
    )

    assert confidence == 0.80


def test_confidence_with_multiple_populated_sources():
    evidence = make_evidence()

    confidence = AquaSenseLLM._estimate_confidence(
        evidence
    )

    assert confidence == 0.90


def test_empty_question_rejected(monkeypatch):
    monkeypatch.setenv(
        "OPENAI_API_KEY",
        "test-key",
    )

    llm = AquaSenseLLM()

    with pytest.raises(ValueError):
        llm.answer(
            "",
            make_evidence(),
        )


def test_whitespace_question_rejected(monkeypatch):
    monkeypatch.setenv(
        "OPENAI_API_KEY",
        "test-key",
    )

    llm = AquaSenseLLM()

    with pytest.raises(ValueError):
        llm.answer(
            "   ",
            make_evidence(),
        )


def test_llm_answer_with_mocked_openai(monkeypatch):
    monkeypatch.setenv(
        "OPENAI_API_KEY",
        "test-key",
    )

    llm = AquaSenseLLM()

    fake_response = SimpleNamespace(
        output_text=(
            "There is one open high-priority maintenance "
            "ticket for FIXTURE-001 caused by a continuous leak."
        )
    )

    def fake_create(**kwargs):
        assert kwargs["model"] == llm.model
        assert "AquaSense operational question" in kwargs["input"]
        assert "TICKET-001" in kwargs["input"]
        assert "FIXTURE-001" in kwargs["input"]
        assert "continuous_leak" in kwargs["input"]

        return fake_response

    monkeypatch.setattr(
        llm.client.responses,
        "create",
        fake_create,
    )

    result = llm.answer(
        "What maintenance issues are currently open?",
        make_evidence(),
    )

    assert result.answer == fake_response.output_text
    assert len(result.evidence) == 2
    assert result.confidence == 0.90


def test_llm_passes_grounded_evidence_to_model(monkeypatch):
    monkeypatch.setenv(
        "OPENAI_API_KEY",
        "test-key",
    )

    llm = AquaSenseLLM()

    captured = {}

    fake_response = SimpleNamespace(
        output_text="Grounded AquaSense response."
    )

    def fake_create(**kwargs):
        captured.update(kwargs)
        return fake_response

    monkeypatch.setattr(
        llm.client.responses,
        "create",
        fake_create,
    )

    evidence = make_evidence()

    result = llm.answer(
        "Explain the current facility situation.",
        evidence,
    )

    assert result.answer == "Grounded AquaSense response."

    assert "maintenance_tickets" in captured["input"]
    assert "recent_telemetry" in captured["input"]

    assert "TICKET-001" in captured["input"]
    assert "FIXTURE-001" in captured["input"]
    assert "82.0" in captured["input"]
    assert "continuous_leak" in captured["input"]


def test_llm_uses_grounding_instructions(monkeypatch):
    monkeypatch.setenv(
        "OPENAI_API_KEY",
        "test-key",
    )

    llm = AquaSenseLLM()

    fake_response = SimpleNamespace(
        output_text="Grounded response."
    )

    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return fake_response

    monkeypatch.setattr(
        llm.client.responses,
        "create",
        fake_create,
    )

    llm.answer(
        "What is happening?",
        make_evidence(),
    )

    instructions = captured["instructions"]

    assert "Never invent telemetry" in instructions
    assert "Use ONLY the operational evidence" in instructions
    assert "when that information exists" in instructions

def test_llm_api_failure_is_handled(monkeypatch):
    monkeypatch.setenv(
        "OPENAI_API_KEY",
        "test-key",
    )

    llm = AquaSenseLLM()

    def fake_create(**kwargs):
        raise RuntimeError("Simulated OpenAI API failure")

    monkeypatch.setattr(
        llm.client.responses,
        "create",
        fake_create,
    )

    with pytest.raises(RuntimeError, match="Simulated OpenAI API failure"):
        llm.answer(
            "What maintenance issues are open?",
            make_evidence(),
        )