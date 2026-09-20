from copilot.context import AquaSenseCopilotContext


def test_context_includes_operational_evidence(repository):
    from copilot.tools import AquaSenseCopilotTools

    tools = AquaSenseCopilotTools(repository)
    context = AquaSenseCopilotContext(tools)

    evidence = context.build_context(
        "What is happening in the facility?"
    )

    sources = {item.source for item in evidence}

    assert "maintenance_tickets" in sources
    assert "recent_telemetry" in sources


def test_context_includes_fixture_evidence(repository):
    from copilot.tools import AquaSenseCopilotTools

    tools = AquaSenseCopilotTools(repository)
    context = AquaSenseCopilotContext(tools)

    evidence = context.build_context(
        "What is happening with this fixture?",
        fixture_id="fixture-001",
    )

    sources = {item.source for item in evidence}

    assert "maintenance_tickets" in sources
    assert "recent_telemetry" in sources
    assert "fixture_telemetry" in sources


def test_empty_question_rejected(repository):
    from copilot.tools import AquaSenseCopilotTools

    tools = AquaSenseCopilotTools(repository)
    context = AquaSenseCopilotContext(tools)

    try:
        context.build_context("")
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError")


def test_invalid_reading_limit_rejected(repository):
    from copilot.tools import AquaSenseCopilotTools

    tools = AquaSenseCopilotTools(repository)
    context = AquaSenseCopilotContext(tools)

    try:
        context.build_context("Show telemetry", reading_limit=0)
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError")