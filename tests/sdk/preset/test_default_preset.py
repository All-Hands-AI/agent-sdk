"""Test default preset functionality."""

import pytest

from openhands.sdk.context.condenser.llm_summarizing_condenser import (
    LLMSummarizingCondenser,
)
from openhands.sdk.llm import LLM
from openhands.sdk.preset.default import get_default_agent
from openhands.sdk.tool.spec import ToolSpec


@pytest.fixture
def basic_llm():
    """Create a basic LLM for testing."""
    return LLM(model="test-model")


def test_get_default_agent_includes_browser_toolset(basic_llm):
    """Test that the default agent spec includes BrowserToolSet."""
    agent = get_default_agent(llm=basic_llm, working_dir="/test")

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
    agent = get_default_agent(llm=basic_llm, working_dir="/test")

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
    agent = get_default_agent(llm=basic_llm, working_dir="/test")

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
    """Test that custom working directory is passed to appropriate tools."""
    custom_dir = "/custom/workspace"
    agent = get_default_agent(llm=basic_llm, working_dir=custom_dir)

    # Find BashTool and TaskTrackerTool to verify they get the working_dir
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

    # BashTool should get the working_dir
    assert bash_tool_spec is not None
    assert bash_tool_spec.params["working_dir"] == custom_dir

    # TaskTrackerTool should get save_dir based on working_dir
    assert task_tracker_spec is not None
    assert task_tracker_spec.params["save_dir"] == f"{custom_dir}/.openhands"

    # BrowserToolSet should not be affected by working_dir
    assert browser_toolset_spec is not None
    assert browser_toolset_spec.params == {}


def test_get_default_agent_has_mcp_config(basic_llm):
    """Test that the default agent spec includes MCP configuration."""
    agent = get_default_agent(llm=basic_llm, working_dir="/test")

    assert agent.mcp_config is not None
    assert "mcpServers" in agent.mcp_config

    # Should have fetch server configured
    assert "fetch" in agent.mcp_config["mcpServers"]
    fetch_config = agent.mcp_config["mcpServers"]["fetch"]
    assert fetch_config["command"] == "uvx"
    assert fetch_config["args"] == ["mcp-server-fetch"]


def test_get_default_agent_basic_properties(basic_llm):
    """Test basic properties of the default agent spec."""
    agent = get_default_agent(llm=basic_llm, working_dir="/test")

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
    agent = get_default_agent(llm=basic_llm, working_dir="/test")

    assert agent.condenser is not None
    assert isinstance(agent.condenser, LLMSummarizingCondenser)
    assert agent.condenser.llm == basic_llm
    assert agent.condenser.max_size == 80
    assert agent.condenser.keep_first == 4


def test_get_default_agent_tool_order(basic_llm):
    """Test that tools are in expected order in the default spec."""
    agent = get_default_agent(llm=basic_llm, working_dir="/test")

    tool_names = [tool.name for tool in agent.tools]

    # BrowserToolSet should be the last tool in the list
    assert tool_names[-1] == "BrowserToolSet"

    # Other tools should come before BrowserToolSet
    expected_order = ["BashTool", "FileEditorTool", "TaskTrackerTool", "BrowserToolSet"]
    assert tool_names == expected_order
