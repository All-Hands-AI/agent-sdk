"""Test BrowserToolSet functionality."""

import tempfile
from uuid import uuid4

from pydantic import SecretStr

from openhands.sdk.agent import Agent
from openhands.sdk.conversation.state import ConversationState
from openhands.sdk.llm import LLM
from openhands.sdk.tool import Tool
from openhands.sdk.tool.tool import ToolBase
from openhands.tools.browser_use import (
    BrowserToolSet,
    browser_click_tool,
    browser_close_tab_tool,
    browser_get_content_tool,
    browser_get_state_tool,
    browser_go_back_tool,
    browser_list_tabs_tool,
    browser_navigate_tool,
    browser_scroll_tool,
    browser_switch_tab_tool,
    browser_type_tool,
)
from openhands.tools.browser_use.impl import BrowserToolExecutor


def _create_test_conv_state(temp_dir: str) -> ConversationState:
    """Helper to create a test conversation state."""
    llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="test-llm")
    agent = Agent(llm=llm, tools=[])
    return ConversationState.create(
        id=uuid4(),
        agent=agent,
        working_dir=temp_dir,
    )


def test_browser_toolset_create_returns_list():
    """Test that BrowserToolSet.create() returns a list of tools."""
    with tempfile.TemporaryDirectory() as temp_dir:
        conv_state = _create_test_conv_state(temp_dir)
        tools = BrowserToolSet.create(conv_state=conv_state)

        assert isinstance(tools, list)
        assert len(tools) == 10  # All browser tools

        # Verify all items are Tool instances
        for tool in tools:
            assert isinstance(tool, Tool)


def test_browser_toolset_create_includes_all_browser_tools():
    """Test that BrowserToolSet.create() includes all expected browser tools."""
    with tempfile.TemporaryDirectory() as temp_dir:
        conv_state = _create_test_conv_state(temp_dir)
        tools = BrowserToolSet.create(conv_state=conv_state)

        # Get tool names
        tool_names = [tool.name for tool in tools]

        # Expected tool names based on the browser tools
        expected_names = [
            browser_navigate_tool.name,
            browser_click_tool.name,
            browser_get_state_tool.name,
            browser_get_content_tool.name,
            browser_type_tool.name,
            browser_scroll_tool.name,
            browser_go_back_tool.name,
            browser_list_tabs_tool.name,
            browser_switch_tab_tool.name,
            browser_close_tab_tool.name,
        ]

        # Verify all expected tools are present
        for expected_name in expected_names:
            assert expected_name in tool_names, f"Missing tool: {expected_name}"

        # Verify no extra tools
        assert len(tool_names) == len(expected_names)


def test_browser_toolset_create_tools_have_shared_executor():
    """Test that all tools from BrowserToolSet.create() share the same executor."""
    with tempfile.TemporaryDirectory() as temp_dir:
        conv_state = _create_test_conv_state(temp_dir)
        tools = BrowserToolSet.create(conv_state=conv_state)

        # Get the executor from the first tool
        first_executor = tools[0].executor
        assert first_executor is not None
        assert isinstance(first_executor, BrowserToolExecutor)

        # Verify all tools share the same executor instance
        for tool in tools:
            assert tool.executor is first_executor


def test_browser_toolset_create_tools_are_properly_configured():
    """Test that tools from BrowserToolSet.create() are properly configured."""
    with tempfile.TemporaryDirectory() as temp_dir:
        conv_state = _create_test_conv_state(temp_dir)
        tools = BrowserToolSet.create(conv_state=conv_state)

        # Find a specific tool to test (e.g., navigate tool)
        navigate_tool = None
        for tool in tools:
            if tool.name == browser_navigate_tool.name:
                navigate_tool = tool
                break

        assert navigate_tool is not None
        assert navigate_tool.description == browser_navigate_tool.description
        assert navigate_tool.action_type == browser_navigate_tool.action_type
        assert navigate_tool.observation_type == browser_navigate_tool.observation_type
        assert navigate_tool.executor is not None


def test_browser_toolset_create_multiple_calls_create_separate_executors():
    """Test that multiple calls to BrowserToolSet.create() create separate executors."""
    with tempfile.TemporaryDirectory() as temp_dir:
        conv_state = _create_test_conv_state(temp_dir)
        tools1 = BrowserToolSet.create(conv_state=conv_state)
        tools2 = BrowserToolSet.create(conv_state=conv_state)

        # Executors should be different instances
        executor1 = tools1[0].executor
        executor2 = tools2[0].executor

        assert executor1 is not executor2
        assert isinstance(executor1, BrowserToolExecutor)
        assert isinstance(executor2, BrowserToolExecutor)


def test_browser_toolset_create_tools_can_generate_mcp_schema():
    """Test that tools from BrowserToolSet.create() can generate MCP schemas."""
    with tempfile.TemporaryDirectory() as temp_dir:
        conv_state = _create_test_conv_state(temp_dir)
        tools = BrowserToolSet.create(conv_state=conv_state)

        for tool in tools:
            mcp_tool = tool.to_mcp_tool()

            # Basic schema validation
            assert "name" in mcp_tool
            assert "description" in mcp_tool
            assert "inputSchema" in mcp_tool
            assert mcp_tool["name"] == tool.name
            assert mcp_tool["description"] == tool.description

            # Schema should have proper structure
            input_schema = mcp_tool["inputSchema"]
            assert input_schema["type"] == "object"
            assert "properties" in input_schema


def test_browser_toolset_create_no_parameters():
    """Test that BrowserToolSet.create() works without parameters."""
    with tempfile.TemporaryDirectory() as temp_dir:
        conv_state = _create_test_conv_state(temp_dir)
        # Should not raise any exceptions
        tools = BrowserToolSet.create(conv_state=conv_state)
        assert len(tools) > 0


def test_browser_toolset_inheritance():
    """Test that BrowserToolSet properly inherits from Tool."""
    assert issubclass(BrowserToolSet, ToolBase)

    # BrowserToolSet should not be instantiable directly (it's a factory)
    # The create method returns a list, not an instance of BrowserToolSet
    with tempfile.TemporaryDirectory() as temp_dir:
        conv_state = _create_test_conv_state(temp_dir)
        tools = BrowserToolSet.create(conv_state=conv_state)
        for tool in tools:
            assert not isinstance(tool, BrowserToolSet)
            assert isinstance(tool, ToolBase)
