
import pytest

from copilot.tools import AquaSenseCopilotTools

def test_open_maintenance_tickets_tool(repository):
    tools = AquaSenseCopilotTools(repository)

    result = tools.get_open_maintenance_tickets()

    assert result.source == "maintenance_tickets"
    assert "count" in result.data
    assert "tickets" in result.data
    assert isinstance(result.data["tickets"], list)


def test_recent_readings_tool(repository):
    tools = AquaSenseCopilotTools(repository)

    result = tools.get_recent_readings(limit=10)

    assert result.source == "recent_telemetry"
    assert result.data["count"] <= 10
    assert isinstance(result.data["readings"], list)


def test_fixture_readings_tool(repository):
    tools = AquaSenseCopilotTools(repository)

    recent = tools.get_recent_readings(limit=1)

    if recent.data["readings"]:
        fixture_id = recent.data["readings"][0]["fixture_id"]

        result = tools.get_fixture_readings(
            fixture_id=fixture_id,
            limit=10,
        )

        assert result.source == "fixture_telemetry"
        assert result.data["fixture_id"] == fixture_id
        assert isinstance(result.data["readings"], list)


def test_invalid_readings_limit(repository):
    tools = AquaSenseCopilotTools(repository)

    with pytest.raises(ValueError):
        tools.get_recent_readings(limit=0)


def test_invalid_fixture_id(repository):
    tools = AquaSenseCopilotTools(repository)

    with pytest.raises(ValueError):
        tools.get_fixture_readings("")