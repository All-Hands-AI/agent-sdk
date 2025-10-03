"""Test planning preset functionality."""

import pytest

from openhands.sdk.context.condenser.llm_summarizing_condenser import (
    LLMSummarizingCondenser,
)
from openhands.sdk.llm import LLM
from openhands.tools.preset.planning import get_planning_agent


@pytest.fixture
def basic_llm():
    """Create a basic LLM for testing."""
    return LLM(model="test-model", service_id="test-llm")


def test_get_planning_agent_includes_expected_tools(basic_llm):
    """Test that the planning agent includes the expected tools."""
    agent = get_planning_agent(llm=basic_llm)

    # Check that expected tools are present
    tool_names = [tool.name for tool in agent.tools]
    expected_tools = ["BashTool", "FileViewerTool", "PlanWriterTool", "TaskTrackerTool"]

    for expected_tool in expected_tools:
        assert expected_tool in tool_names


def test_get_planning_agent_uses_planning_system_prompt(basic_llm):
    """Test that the planning agent uses the planning system prompt."""
    agent = get_planning_agent(llm=basic_llm)

    # Check that the planning system prompt is used
    assert agent.system_prompt_filename == "planning_system_prompt.j2"


def test_get_planning_agent_has_mcp_config(basic_llm):
    """Test that the planning agent has MCP configuration."""
    agent = get_planning_agent(llm=basic_llm)

    # Check MCP configuration
    assert agent.mcp_config is not None
    assert "mcpServers" in agent.mcp_config
    assert "fetch" in agent.mcp_config["mcpServers"]
    assert "repomix" in agent.mcp_config["mcpServers"]


def test_get_planning_agent_has_filter_tools_regex(basic_llm):
    """Test that the planning agent has filter tools regex."""
    agent = get_planning_agent(llm=basic_llm)

    # Check filter tools regex is set
    assert agent.filter_tools_regex is not None
    assert "repomix" in agent.filter_tools_regex


def test_get_planning_agent_condenser_config(basic_llm):
    """Test that the planning agent has proper condenser configuration."""
    agent = get_planning_agent(llm=basic_llm)

    # Check condenser configuration
    assert agent.condenser is not None
    assert isinstance(agent.condenser, LLMSummarizingCondenser)

    # Planning agents should have larger context window
    assert agent.condenser.max_size == 100
    assert agent.condenser.keep_first == 6


def test_get_planning_agent_has_no_security_analyzer(basic_llm):
    """Test that the planning agent has security analyzer by default."""
    agent = get_planning_agent(llm=basic_llm)

    # Check security analyzer
    assert agent.security_analyzer is None


def test_get_planning_agent_basic_properties(basic_llm):
    """Test basic properties of the planning agent."""
    agent = get_planning_agent(llm=basic_llm)

    # Check basic properties
    assert agent.llm == basic_llm
    assert (
        len(agent.tools) == 4
    )  # BashTool, FileViewerTool, PlanWriterTool, TaskTrackerTool

    # Check condenser LLM service ID
    assert isinstance(agent.condenser, LLMSummarizingCondenser)
    assert agent.condenser.llm.service_id == "planning_condenser"
