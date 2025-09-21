"""Test Agent.from_spec functionality."""

from unittest.mock import patch

import pytest

from openhands.sdk.agent import Agent
from openhands.sdk.agent.spec import AgentSpec
from openhands.sdk.context.agent_context import AgentContext
from openhands.sdk.context.condenser.llm_summarizing_condenser import (
    LLMSummarizingCondenser,
)
from openhands.sdk.context.condenser.no_op_condenser import NoOpCondenser
from openhands.sdk.llm import LLM
from openhands.sdk.tool import Tool
from openhands.sdk.tool.schema import ActionBase, ObservationBase
from openhands.sdk.tool.spec import ToolSpec
from openhands.sdk.tool.tool import ToolAnnotations, ToolExecutor


def get_tools_list(tools):
    """Helper to get tools as a list regardless of whether they're dict or sequence."""
    return list(tools.values()) if isinstance(tools, dict) else list(tools)


class TestAgentFromSpecMockAction(ActionBase):
    """Mock action for testing."""

    pass


class TestAgentFromSpecMockObservation(ObservationBase):
    """Mock observation for testing."""

    pass


class MockExecutor(ToolExecutor):
    """Mock executor for testing."""

    def __call__(
        self, action: TestAgentFromSpecMockAction
    ) -> TestAgentFromSpecMockObservation:
        return TestAgentFromSpecMockObservation()


def create_mock_tool(name: str) -> Tool:
    """Create a mock tool that behaves like a Tool instance."""
    return Tool(
        name=name,
        action_type=TestAgentFromSpecMockAction,
        observation_type=TestAgentFromSpecMockObservation,
        description=f"Mock tool {name}",
        executor=MockExecutor(),
        annotations=ToolAnnotations(title=name),
    )


def create_mock_condenser() -> NoOpCondenser:
    """Create a mock condenser that behaves like a CondenserBase instance."""
    return NoOpCondenser()


@pytest.fixture
def basic_llm():
    """Create a basic LLM for testing."""
    return LLM(model="test-model")


@pytest.fixture
def basic_agent_spec(basic_llm):
    """Create a basic AgentSpec for testing."""
    return AgentSpec(llm=basic_llm)


def test_from_spec_basic_agent_creation(basic_agent_spec):
    """Test creating an agent from a basic spec."""
    agent = Agent.from_spec(basic_agent_spec)

    assert isinstance(agent, Agent)
    assert agent.llm.model == "test-model"
    # Agent has built-in tools (finish, think)
    assert len(agent.tools) == 2
    assert "finish" in agent.tools
    assert "think" in agent.tools
    assert agent.agent_context is None
    assert agent.system_prompt_filename == "system_prompt.j2"
    assert agent.system_prompt_kwargs == {}
    assert agent.condenser is None


def test_from_spec_with_tools(basic_llm):
    """Test creating an agent with tools from spec."""
    tool_specs = [
        ToolSpec(name="BashTool", params={"working_dir": "/workspace"}),
        ToolSpec(name="FileEditorTool", params={}),
    ]

    spec = AgentSpec(llm=basic_llm, tools=tool_specs)

    with (
        patch("openhands.tools.BashTool") as mock_bash_tool,
        patch("openhands.tools.FileEditorTool") as mock_file_tool,
    ):
        # Mock the create methods
        mock_bash_instance = create_mock_tool("bash_tool")
        mock_file_instance = create_mock_tool("file_editor_tool")
        mock_bash_tool.create.return_value = mock_bash_instance
        mock_file_tool.create.return_value = mock_file_instance

        agent = Agent.from_spec(spec)

        # Verify tools were created with correct parameters
        mock_bash_tool.create.assert_called_once_with(working_dir="/workspace")
        mock_file_tool.create.assert_called_once_with()

        # Verify tools are in the agent (2 custom + 2 built-in)
        assert len(agent.tools) == 4
        tools_list = get_tools_list(agent.tools)
        assert mock_bash_instance in tools_list
        assert mock_file_instance in tools_list
        assert "finish" in agent.tools
        assert "think" in agent.tools


def test_from_spec_with_unknown_tool(basic_llm):
    """Test that unknown tools are skipped gracefully."""
    tool_specs = [
        ToolSpec(name="UnknownTool", params={}),
        ToolSpec(name="BashTool", params={"working_dir": "/workspace"}),
    ]

    spec = AgentSpec(llm=basic_llm, tools=tool_specs)

    with patch("openhands.tools.BashTool") as mock_bash_tool:
        mock_bash_instance = create_mock_tool("bash_tool")
        mock_bash_tool.create.return_value = mock_bash_instance

        with pytest.raises(
            ValueError,
            match="Unknown tool name: UnknownTool. Not found in openhands.tools",
        ):
            Agent.from_spec(spec)


def test_from_spec_with_mcp_config(basic_llm):
    """Test creating an agent with MCP configuration."""
    # Note: Due to current implementation, MCP tools are only created if there are
    # tool_specs
    # So we need to include at least one tool spec for MCP to be processed
    tool_specs = [
        ToolSpec(name="BashTool", params={"working_dir": "/workspace"}),
    ]
    mcp_config = {
        "mcpServers": {"fetch": {"command": "uvx", "args": ["mcp-server-fetch"]}}
    }

    spec = AgentSpec(llm=basic_llm, tools=tool_specs, mcp_config=mcp_config)

    with (
        patch("openhands.tools.BashTool") as mock_bash_tool,
        patch("openhands.sdk.mcp.create_mcp_tools") as mock_create_mcp,
    ):
        mock_bash_instance = create_mock_tool("bash_tool")
        mock_mcp_tool = create_mock_tool("mcp_tool")

        mock_bash_tool.create.return_value = mock_bash_instance
        mock_create_mcp.return_value = [mock_mcp_tool]

        agent = Agent.from_spec(spec)

        # Verify MCP tools were created (1 bash + 1 MCP + 2 built-in)
        mock_create_mcp.assert_called_once_with(mcp_config, timeout=30)
        assert len(agent.tools) == 4
        tools_list = get_tools_list(agent.tools)
        assert mock_mcp_tool in tools_list
        assert mock_bash_instance in tools_list
        assert "finish" in agent.tools
        assert "think" in agent.tools


def test_from_spec_with_agent_context(basic_llm):
    """Test creating an agent with agent context."""
    agent_context = AgentContext(
        microagents=[],
        system_message_suffix="Test suffix",
        user_message_suffix="Test prefix",
    )

    spec = AgentSpec(llm=basic_llm, agent_context=agent_context)
    agent = Agent.from_spec(spec)

    assert agent.agent_context == agent_context
    assert agent.agent_context is not None
    assert agent.agent_context.system_message_suffix == "Test suffix"
    assert agent.agent_context.user_message_suffix == "Test prefix"


def test_from_spec_with_system_prompt_config(basic_llm):
    """Test creating an agent with custom system prompt configuration."""
    spec = AgentSpec(
        llm=basic_llm,
        system_prompt_filename="custom_prompt.j2",
        system_prompt_kwargs={"cli_mode": True, "debug": False},
    )

    agent = Agent.from_spec(spec)

    assert agent.system_prompt_filename == "custom_prompt.j2"
    assert agent.system_prompt_kwargs == {"cli_mode": True, "debug": False}


def test_from_spec_with_condenser(basic_llm):
    """Test creating an agent with a condenser."""
    condenser = LLMSummarizingCondenser(llm=basic_llm, max_size=80, keep_first=10)

    spec = AgentSpec(llm=basic_llm, condenser=condenser)
    agent = Agent.from_spec(spec)

    # Verify condenser was set correctly
    assert agent.condenser == condenser


def test_from_spec_without_condenser(basic_llm):
    """Test creating an agent without a condenser."""
    spec = AgentSpec(llm=basic_llm, condenser=None)
    agent = Agent.from_spec(spec)

    assert agent.condenser is None


def test_from_spec_comprehensive(basic_llm):
    """Test creating an agent with all possible configurations."""
    agent_context = AgentContext(
        microagents=[], system_message_suffix="Comprehensive test"
    )

    tool_specs = [
        ToolSpec(name="BashTool", params={"working_dir": "/test"}),
    ]

    condenser = NoOpCondenser()

    mcp_config = {"mcpServers": {"test": {"command": "test"}}}

    spec = AgentSpec(
        llm=basic_llm,
        tools=tool_specs,
        mcp_config=mcp_config,
        agent_context=agent_context,
        system_prompt_filename="comprehensive.j2",
        system_prompt_kwargs={"mode": "test"},
        condenser=condenser,
    )

    with (
        patch("openhands.tools.BashTool") as mock_bash_tool,
        patch("openhands.sdk.mcp.create_mcp_tools") as mock_create_mcp,
    ):
        mock_bash_instance = create_mock_tool("bash_tool")
        mock_mcp_tool = create_mock_tool("mcp_tool")

        mock_bash_tool.create.return_value = mock_bash_instance
        mock_create_mcp.return_value = [mock_mcp_tool]

        agent = Agent.from_spec(spec)

        # Verify all components were created correctly
        assert agent.llm == basic_llm
        assert len(agent.tools) == 4  # BashTool + MCP tool + 2 built-in
        assert agent.agent_context == agent_context
        assert agent.system_prompt_filename == "comprehensive.j2"
        assert agent.system_prompt_kwargs == {"mode": "test"}
        assert agent.condenser == condenser

        # Verify method calls
        mock_bash_tool.create.assert_called_once_with(working_dir="/test")
        mock_create_mcp.assert_called_once_with(mcp_config, timeout=30)


def test_from_spec_tools_and_mcp_combined(basic_llm):
    """Test that both regular tools and MCP tools are combined correctly."""
    tool_specs = [
        ToolSpec(name="BashTool", params={}),
        ToolSpec(name="FileEditorTool", params={}),
    ]

    mcp_config = {"mcpServers": {"test": {"command": "test"}}}

    spec = AgentSpec(llm=basic_llm, tools=tool_specs, mcp_config=mcp_config)

    with (
        patch("openhands.tools.BashTool") as mock_bash_tool,
        patch("openhands.tools.FileEditorTool") as mock_file_tool,
        patch("openhands.sdk.mcp.create_mcp_tools") as mock_create_mcp,
    ):
        mock_bash_instance = create_mock_tool("bash_tool")
        mock_file_instance = create_mock_tool("file_editor_tool")
        mock_mcp_tool1 = create_mock_tool("mcp_tool1")
        mock_mcp_tool2 = create_mock_tool("mcp_tool2")

        mock_bash_tool.create.return_value = mock_bash_instance
        mock_file_tool.create.return_value = mock_file_instance
        mock_create_mcp.return_value = [mock_mcp_tool1, mock_mcp_tool2]

        agent = Agent.from_spec(spec)

        # Should have 6 tools total: 2 regular + 2 MCP + 2 built-in
        assert len(agent.tools) == 6
        tools_list = get_tools_list(agent.tools)
        assert mock_bash_instance in tools_list
        assert mock_file_instance in tools_list
        assert mock_mcp_tool1 in tools_list
        assert mock_mcp_tool2 in tools_list
        assert "finish" in agent.tools
        assert "think" in agent.tools


def test_from_spec_with_filter_tools_regex(basic_llm):
    """Test creating an agent with filter_tools_regex to filter tools by name."""
    tool_specs = [
        ToolSpec(name="BashTool", params={}),
        ToolSpec(name="FileEditorTool", params={}),
    ]

    # Filter to only include tools starting with "bash"
    spec = AgentSpec(llm=basic_llm, tools=tool_specs, filter_tools_regex=r"^bash.*")

    with (
        patch("openhands.tools.BashTool") as mock_bash_tool,
        patch("openhands.tools.FileEditorTool") as mock_file_tool,
    ):
        mock_bash_instance = create_mock_tool("bash_tool")
        mock_file_instance = create_mock_tool("file_editor_tool")

        mock_bash_tool.create.return_value = mock_bash_instance
        mock_file_tool.create.return_value = mock_file_instance

        agent = Agent.from_spec(spec)

        # Should have 3 tools total: 1 filtered tool + 2 built-in
        # (file_editor_tool should be filtered out)
        assert len(agent.tools) == 3
        tools_list = get_tools_list(agent.tools)
        assert mock_bash_instance in tools_list
        assert mock_file_instance not in tools_list
        assert "finish" in agent.tools
        assert "think" in agent.tools


def test_from_spec_with_filter_tools_regex_no_matches(basic_llm):
    """Test filter_tools_regex that matches no tools."""
    tool_specs = [
        ToolSpec(name="BashTool", params={}),
        ToolSpec(name="FileEditorTool", params={}),
    ]

    # Filter that matches no tools
    spec = AgentSpec(
        llm=basic_llm, tools=tool_specs, filter_tools_regex=r"^nonexistent.*"
    )

    with (
        patch("openhands.tools.BashTool") as mock_bash_tool,
        patch("openhands.tools.FileEditorTool") as mock_file_tool,
    ):
        mock_bash_instance = create_mock_tool("bash_tool")
        mock_file_instance = create_mock_tool("file_editor_tool")

        mock_bash_tool.create.return_value = mock_bash_instance
        mock_file_tool.create.return_value = mock_file_instance

        agent = Agent.from_spec(spec)

        # Should have only 2 built-in tools (all custom tools filtered out)
        assert len(agent.tools) == 2
        tools_list = get_tools_list(agent.tools)
        assert mock_bash_instance not in tools_list
        assert mock_file_instance not in tools_list
        assert "finish" in agent.tools
        assert "think" in agent.tools


def test_from_spec_with_filter_tools_regex_and_mcp(basic_llm):
    """Test filter_tools_regex with both regular tools and MCP tools."""
    tool_specs = [
        ToolSpec(name="BashTool", params={}),
        ToolSpec(name="FileEditorTool", params={}),
    ]

    mcp_config = {"mcpServers": {"test": {"command": "test"}}}

    # Filter to include tools starting with "bash" or "mcp"
    spec = AgentSpec(
        llm=basic_llm,
        tools=tool_specs,
        mcp_config=mcp_config,
        filter_tools_regex=r"^(bash|mcp).*",
    )

    with (
        patch("openhands.tools.BashTool") as mock_bash_tool,
        patch("openhands.tools.FileEditorTool") as mock_file_tool,
        patch("openhands.sdk.mcp.create_mcp_tools") as mock_create_mcp,
    ):
        mock_bash_instance = create_mock_tool("bash_tool")
        mock_file_instance = create_mock_tool("file_editor_tool")
        mock_mcp_tool1 = create_mock_tool("mcp_tool1")
        mock_mcp_tool2 = create_mock_tool("mcp_tool2")

        mock_bash_tool.create.return_value = mock_bash_instance
        mock_file_tool.create.return_value = mock_file_instance
        mock_create_mcp.return_value = [mock_mcp_tool1, mock_mcp_tool2]

        agent = Agent.from_spec(spec)

        # Should have 5 tools total: 1 bash + 2 MCP + 2 built-in
        # (file_editor_tool should be filtered out)
        assert len(agent.tools) == 5
        tools_list = get_tools_list(agent.tools)
        assert mock_bash_instance in tools_list
        assert mock_file_instance not in tools_list
        assert mock_mcp_tool1 in tools_list
        assert mock_mcp_tool2 in tools_list
        assert "finish" in agent.tools
        assert "think" in agent.tools


def test_from_spec_with_filter_tools_regex_complex_pattern(basic_llm):
    """Test filter_tools_regex with a complex regex pattern."""
    tool_specs = [
        ToolSpec(name="BashTool", params={}),
        ToolSpec(name="FileEditorTool", params={}),
    ]

    mcp_config = {"mcpServers": {"test": {"command": "test"}}}

    # Complex pattern: exclude tools starting with "file" but include everything else
    spec = AgentSpec(
        llm=basic_llm,
        tools=tool_specs,
        mcp_config=mcp_config,
        filter_tools_regex=r"^(?!file).*",
    )

    with (
        patch("openhands.tools.BashTool") as mock_bash_tool,
        patch("openhands.tools.FileEditorTool") as mock_file_tool,
        patch("openhands.sdk.mcp.create_mcp_tools") as mock_create_mcp,
    ):
        mock_bash_instance = create_mock_tool("bash_tool")
        mock_file_instance = create_mock_tool("file_editor_tool")
        mock_mcp_tool1 = create_mock_tool("mcp_tool1")

        mock_bash_tool.create.return_value = mock_bash_instance
        mock_file_tool.create.return_value = mock_file_instance
        mock_create_mcp.return_value = [mock_mcp_tool1]

        agent = Agent.from_spec(spec)

        # Should have 4 tools total: 1 bash + 1 MCP + 2 built-in
        # (file_editor_tool should be filtered out)
        assert len(agent.tools) == 4
        tools_list = get_tools_list(agent.tools)
        assert mock_bash_instance in tools_list
        assert mock_file_instance not in tools_list
        assert mock_mcp_tool1 in tools_list
        assert "finish" in agent.tools
        assert "think" in agent.tools


def test_from_spec_with_toolset_returning_list(basic_llm):
    """Test creating an agent with a toolset that returns a list of tools."""
    tool_specs = [
        ToolSpec(name="BrowserToolSet", params={}),
    ]

    spec = AgentSpec(llm=basic_llm, tools=tool_specs)

    with patch("openhands.tools.BrowserToolSet") as mock_browser_toolset:
        # Mock the create method to return a list of tools
        mock_tool1 = create_mock_tool("browser_tool1")
        mock_tool2 = create_mock_tool("browser_tool2")
        mock_tool3 = create_mock_tool("browser_tool3")
        mock_browser_toolset.create.return_value = [mock_tool1, mock_tool2, mock_tool3]

        agent = Agent.from_spec(spec)

        # Verify toolset create was called
        mock_browser_toolset.create.assert_called_once_with()

        # Should have 5 tools total: 3 from toolset + 2 built-in
        assert len(agent.tools) == 5
        tools_list = get_tools_list(agent.tools)
        assert mock_tool1 in tools_list
        assert mock_tool2 in tools_list
        assert mock_tool3 in tools_list
        assert "finish" in agent.tools
        assert "think" in agent.tools


def test_from_spec_with_mixed_tools_and_toolsets(basic_llm):
    """Test creating an agent with both regular tools and toolsets."""
    tool_specs = [
        ToolSpec(name="BashTool", params={"working_dir": "/workspace"}),
        ToolSpec(name="BrowserToolSet", params={}),
        ToolSpec(name="FileEditorTool", params={}),
    ]

    spec = AgentSpec(llm=basic_llm, tools=tool_specs)

    with (
        patch("openhands.tools.BashTool") as mock_bash_tool,
        patch("openhands.tools.BrowserToolSet") as mock_browser_toolset,
        patch("openhands.tools.FileEditorTool") as mock_file_tool,
    ):
        # Mock regular tools
        mock_bash_instance = create_mock_tool("bash_tool")
        mock_file_instance = create_mock_tool("file_editor_tool")
        mock_bash_tool.create.return_value = mock_bash_instance
        mock_file_tool.create.return_value = mock_file_instance

        # Mock toolset returning list
        mock_browser_tool1 = create_mock_tool("browser_tool1")
        mock_browser_tool2 = create_mock_tool("browser_tool2")
        mock_browser_toolset.create.return_value = [
            mock_browser_tool1,
            mock_browser_tool2,
        ]

        agent = Agent.from_spec(spec)

        # Verify all create methods were called
        mock_bash_tool.create.assert_called_once_with(working_dir="/workspace")
        mock_browser_toolset.create.assert_called_once_with()
        mock_file_tool.create.assert_called_once_with()

        # Should have 6 tools total: 1 bash + 2 browser + 1 file + 2 built-in
        assert len(agent.tools) == 6
        tools_list = get_tools_list(agent.tools)
        assert mock_bash_instance in tools_list
        assert mock_browser_tool1 in tools_list
        assert mock_browser_tool2 in tools_list
        assert mock_file_instance in tools_list
        assert "finish" in agent.tools
        assert "think" in agent.tools


def test_from_spec_with_empty_toolset(basic_llm):
    """Test creating an agent with a toolset that returns an empty list."""
    tool_specs = [
        ToolSpec(name="BrowserToolSet", params={}),
    ]

    spec = AgentSpec(llm=basic_llm, tools=tool_specs)

    with patch("openhands.tools.BrowserToolSet") as mock_browser_toolset:
        # Mock the create method to return an empty list
        mock_browser_toolset.create.return_value = []

        agent = Agent.from_spec(spec)

        # Verify toolset create was called
        mock_browser_toolset.create.assert_called_once_with()

        # Should have only 2 built-in tools
        assert len(agent.tools) == 2
        assert "finish" in agent.tools
        assert "think" in agent.tools


def test_from_spec_tool_type_validation_success(basic_llm):
    """Test that tool type validation passes for valid Tool instances."""
    tool_specs = [
        ToolSpec(name="BashTool", params={}),
    ]

    spec = AgentSpec(llm=basic_llm, tools=tool_specs)

    with patch("openhands.tools.BashTool") as mock_bash_tool:
        mock_bash_instance = create_mock_tool("bash_tool")
        mock_bash_tool.create.return_value = mock_bash_instance

        # Should not raise any exceptions
        agent = Agent.from_spec(spec)
        assert len(agent.tools) == 3  # 1 bash + 2 built-in


def test_from_spec_tool_type_validation_failure_single_tool(basic_llm):
    """Test that tool type validation fails for invalid tool types from single tool."""
    tool_specs = [
        ToolSpec(name="BashTool", params={}),
    ]

    spec = AgentSpec(llm=basic_llm, tools=tool_specs)

    with patch("openhands.tools.BashTool") as mock_bash_tool:
        # Mock create to return a non-Tool object
        mock_bash_tool.create.return_value = "not_a_tool"

        with pytest.raises(
            ValueError,
            match=(
                r"Tool not_a_tool is not an instance of 'Tool'\. "
                r"Got type: <class 'str'>"
            ),
        ):
            Agent.from_spec(spec)


def test_from_spec_tool_type_validation_failure_toolset(basic_llm):
    """Test that tool type validation fails for invalid tool types from toolset."""
    tool_specs = [
        ToolSpec(name="BrowserToolSet", params={}),
    ]

    spec = AgentSpec(llm=basic_llm, tools=tool_specs)

    with patch("openhands.tools.BrowserToolSet") as mock_browser_toolset:
        # Mock create to return a list with invalid tool types
        mock_valid_tool = create_mock_tool("valid_tool")
        mock_browser_toolset.create.return_value = [
            mock_valid_tool,
            "invalid_tool",
            123,
        ]

        with pytest.raises(
            ValueError,
            match=(
                r"Tool invalid_tool is not an instance of 'Tool'\. "
                r"Got type: <class 'str'>"
            ),
        ):
            Agent.from_spec(spec)


def test_from_spec_toolset_with_mcp_and_filtering(basic_llm):
    """Test toolset integration with MCP tools and filtering."""
    tool_specs = [
        ToolSpec(name="BashTool", params={}),
        ToolSpec(name="BrowserToolSet", params={}),
    ]

    mcp_config = {"mcpServers": {"test": {"command": "test"}}}

    # Filter to include tools starting with "bash" or "browser"
    spec = AgentSpec(
        llm=basic_llm,
        tools=tool_specs,
        mcp_config=mcp_config,
        filter_tools_regex=r"^(bash|browser).*",
    )

    with (
        patch("openhands.tools.BashTool") as mock_bash_tool,
        patch("openhands.tools.BrowserToolSet") as mock_browser_toolset,
        patch("openhands.sdk.mcp.create_mcp_tools") as mock_create_mcp,
    ):
        # Mock regular tool
        mock_bash_instance = create_mock_tool("bash_tool")
        mock_bash_tool.create.return_value = mock_bash_instance

        # Mock toolset returning list
        mock_browser_tool1 = create_mock_tool("browser_tool1")
        mock_browser_tool2 = create_mock_tool("browser_tool2")
        mock_browser_toolset.create.return_value = [
            mock_browser_tool1,
            mock_browser_tool2,
        ]

        # Mock MCP tools
        mock_mcp_tool = create_mock_tool("mcp_tool")
        mock_create_mcp.return_value = [mock_mcp_tool]

        agent = Agent.from_spec(spec)

        # Should have 5 tools total: 1 bash + 2 browser + 2 built-in
        # MCP tool is filtered out because it doesn't match the regex pattern
        assert len(agent.tools) == 5
        tools_list = get_tools_list(agent.tools)
        assert mock_bash_instance in tools_list
        assert mock_browser_tool1 in tools_list
        assert mock_browser_tool2 in tools_list
        # MCP tool should be filtered out by the regex
        assert mock_mcp_tool not in tools_list
        assert "finish" in agent.tools
        assert "think" in agent.tools
