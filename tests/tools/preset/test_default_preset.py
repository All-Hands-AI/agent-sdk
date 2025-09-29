"""Test default preset functionality."""

import pytest

from openhands.sdk.context.condenser.llm_summarizing_condenser import (
    LLMSummarizingCondenser,
)
from openhands.sdk.llm import LLM
from openhands.sdk.security.llm_analyzer import LLMSecurityAnalyzer
from openhands.sdk.tool.spec import ToolSpec
from openhands.tools.preset.default import get_default_agent


@pytest.fixture
def basic_llm():
    """Create a basic LLM for testing."""
    return LLM(model="test-model", service_id="test-llm")


def test_get_default_agent_includes_browser_toolset(basic_llm):
    """Test that the default agent spec includes BrowserToolSet."""
    agent = get_default_agent(llm=basic_llm)

    # Check that BrowserToolSet is in the tools
    tool_names = [tool.name for tool in agent.tools]
    assert "BrowserToolSet" in tool_names

    # Find the BrowserToolSet spec
    browser_toolset_spec = None
    for tool in agent.tools:
        if tool.name == "BrowserToolSet":
            browser_toolset_spec = tool
            break

    assert browser_toolset_spec is not None
    assert isinstance(browser_toolset_spec, ToolSpec)
    assert browser_toolset_spec.params == {}


def test_get_default_agent_includes_expected_tools(basic_llm):
    """Test that the default agent spec includes all expected tools."""
    agent = get_default_agent(llm=basic_llm)

    tool_names = [tool.name for tool in agent.tools]

    # Expected tools based on the default preset
    expected_tools = [
        "BashTool",
        "FileEditorTool",
        "TaskTrackerTool",
        "BrowserToolSet",
    ]

    for expected_tool in expected_tools:
        assert expected_tool in tool_names, f"Missing expected tool: {expected_tool}"


def test_get_default_agent_browser_toolset_parameters(basic_llm):
    """Test that BrowserToolSet in default spec has correct parameters."""
    agent = get_default_agent(llm=basic_llm)

    # Find the BrowserToolSet spec
    browser_toolset_spec = None
    for tool in agent.tools:
        if tool.name == "BrowserToolSet":
            browser_toolset_spec = tool
            break

    assert browser_toolset_spec is not None
    # BrowserToolSet should have empty params (no customization needed)
    assert browser_toolset_spec.params == {}


def test_get_default_agent_with_custom_working_dir(basic_llm):
    """Test that tools no longer have explicit directory parameters (they get them from conversation)."""  # noqa: E501
    agent = get_default_agent(llm=basic_llm)

    # Find BashTool and TaskTrackerTool to verify they have no directory params
    bash_tool_spec = None
    task_tracker_spec = None
    browser_toolset_spec = None

    for tool in agent.tools:
        if tool.name == "BashTool":
            bash_tool_spec = tool
        elif tool.name == "TaskTrackerTool":
            task_tracker_spec = tool
        elif tool.name == "BrowserToolSet":
            browser_toolset_spec = tool

    # Tools should not have directory parameters - they get them from conversation
    assert bash_tool_spec is not None
    assert bash_tool_spec.params == {}

    assert task_tracker_spec is not None
    assert task_tracker_spec.params == {}

    # BrowserToolSet should also have no params
    assert browser_toolset_spec is not None
    assert browser_toolset_spec.params == {}


def test_get_default_agent_has_mcp_config(basic_llm):
    """Test that the default agent spec includes MCP configuration."""
    agent = get_default_agent(llm=basic_llm)

    assert agent.mcp_config is not None
    assert "mcpServers" in agent.mcp_config

    # Should have fetch server configured
    assert "fetch" in agent.mcp_config["mcpServers"]
    fetch_config = agent.mcp_config["mcpServers"]["fetch"]
    assert fetch_config["command"] == "uvx"
    assert fetch_config["args"] == ["mcp-server-fetch"]


def test_get_default_agent_basic_properties(basic_llm):
    """Test basic properties of the default agent spec."""
    agent = get_default_agent(llm=basic_llm)

    # Should have the provided LLM
    assert agent.llm == basic_llm

    # Should have tools
    assert len(agent.tools) > 0

    # Should have MCP config
    assert agent.mcp_config is not None

    # Other properties should have reasonable defaults
    assert agent.agent_context is None  # No custom agent context by default
    assert agent.condenser is not None  # Has condenser by default
    assert agent.filter_tools_regex is not None  # Has filtering for repomix tools


def test_get_default_agent_condenser_config(basic_llm):
    """Test that the default agent spec has proper condenser configuration."""
    agent = get_default_agent(llm=basic_llm)

    assert agent.condenser is not None
    assert isinstance(agent.condenser, LLMSummarizingCondenser)
    assert basic_llm.service_id != agent.condenser.llm.service_id
    assert agent.condenser.llm == basic_llm.model_copy(
        update={"service_id": "condenser"}
    )  # Condenser LLM should have service_id set
    assert agent.condenser.max_size == 80
    assert agent.condenser.keep_first == 4


def test_get_default_agent_tool_order(basic_llm):
    """Test that tools are in expected order in the default spec."""
    agent = get_default_agent(llm=basic_llm)

    tool_names = [tool.name for tool in agent.tools]

    # BrowserToolSet should be the last tool in the list
    assert tool_names[-1] == "BrowserToolSet"

    # Other tools should come before BrowserToolSet
    expected_order = ["BashTool", "FileEditorTool", "TaskTrackerTool", "BrowserToolSet"]
    assert tool_names == expected_order


def test_get_default_agent_with_custom_persistence_dir(basic_llm):
    """Test that tools no longer have explicit persistence directory parameters."""

    # Test with custom persistence_dir
    agent = get_default_agent(llm=basic_llm)

    # Find TaskTrackerTool to verify it has no directory params
    task_tracker_spec = None
    for tool in agent.tools:
        if tool.name == "TaskTrackerTool":
            task_tracker_spec = tool
            break

    assert task_tracker_spec is not None
    assert (
        task_tracker_spec.params == {}
    )  # No directory params - gets from conversation

    # Test without persistence_dir (should still have no params)
    agent_default = get_default_agent(llm=basic_llm)

    task_tracker_spec_default = None
    for tool in agent_default.tools:
        if tool.name == "TaskTrackerTool":
            task_tracker_spec_default = tool
            break

    assert task_tracker_spec_default is not None
    assert (
        task_tracker_spec_default.params == {}
    )  # No directory params - gets from conversation


def test_get_default_agent_has_llm_security_analyzer(basic_llm):
    """Test that the default agent includes LLMSecurityAnalyzer by default."""
    agent = get_default_agent(llm=basic_llm)

    # Should have LLMSecurityAnalyzer as the security analyzer
    assert agent.security_analyzer is not None
    assert isinstance(agent.security_analyzer, LLMSecurityAnalyzer)
