"""Test Agent.from_spec functionality."""

from unittest.mock import patch

import pytest

from openhands.sdk.agent import Agent
from openhands.sdk.agent.spec import AgentSpec
from openhands.sdk.context.agent_context import AgentContext
from openhands.sdk.context.condenser.no_op_condenser import NoOpCondenser
from openhands.sdk.context.condenser.spec import CondenserSpec
from openhands.sdk.llm import LLM
from openhands.sdk.tool import Tool
from openhands.sdk.tool.schema import ActionBase, ObservationBase
from openhands.sdk.tool.spec import ToolSpec
from openhands.sdk.tool.tool import ToolAnnotations, ToolExecutor


def get_tools_list(tools):
    """Helper to get tools as a list regardless of whether they're dict or sequence."""
    return list(tools.values()) if isinstance(tools, dict) else list(tools)


class MockAction(ActionBase):
    """Mock action for testing."""

    pass


class MockObservation(ObservationBase):
    """Mock observation for testing."""

    pass


class MockExecutor(ToolExecutor):
    """Mock executor for testing."""

    def __call__(self, action: MockAction) -> MockObservation:
        return MockObservation()


def create_mock_tool(name: str) -> Tool:
    """Create a mock tool that behaves like a Tool instance."""
    return Tool(
        name=name,
        action_type=MockAction,
        observation_type=MockObservation,
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
    condenser_spec = CondenserSpec(
        name="LLMSummarizingCondenser",
        params={"llm": basic_llm, "max_size": 80, "keep_first": 10},
    )

    spec = AgentSpec(llm=basic_llm, condenser=condenser_spec)

    with patch(
        "openhands.sdk.context.condenser.base.CondenserBase.from_spec"
    ) as mock_from_spec:
        mock_condenser = create_mock_condenser()
        mock_from_spec.return_value = mock_condenser

        agent = Agent.from_spec(spec)

        # Verify condenser was created from spec
        mock_from_spec.assert_called_once_with(condenser_spec)
        assert agent.condenser == mock_condenser


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

    condenser_spec = CondenserSpec(name="NoOpCondenser", params={})

    mcp_config = {"mcpServers": {"test": {"command": "test"}}}

    spec = AgentSpec(
        llm=basic_llm,
        tools=tool_specs,
        mcp_config=mcp_config,
        agent_context=agent_context,
        system_prompt_filename="comprehensive.j2",
        system_prompt_kwargs={"mode": "test"},
        condenser=condenser_spec,
    )

    with (
        patch("openhands.tools.BashTool") as mock_bash_tool,
        patch("openhands.sdk.mcp.create_mcp_tools") as mock_create_mcp,
        patch(
            "openhands.sdk.context.condenser.base.CondenserBase.from_spec"
        ) as mock_condenser_from_spec,
    ):
        mock_bash_instance = create_mock_tool("bash_tool")
        mock_mcp_tool = create_mock_tool("mcp_tool")
        mock_condenser = create_mock_condenser()

        mock_bash_tool.create.return_value = mock_bash_instance
        mock_create_mcp.return_value = [mock_mcp_tool]
        mock_condenser_from_spec.return_value = mock_condenser

        agent = Agent.from_spec(spec)

        # Verify all components were created correctly
        assert agent.llm == basic_llm
        assert len(agent.tools) == 4  # BashTool + MCP tool + 2 built-in
        assert agent.agent_context == agent_context
        assert agent.system_prompt_filename == "comprehensive.j2"
        assert agent.system_prompt_kwargs == {"mode": "test"}
        assert agent.condenser == mock_condenser

        # Verify method calls
        mock_bash_tool.create.assert_called_once_with(working_dir="/test")
        mock_create_mcp.assert_called_once_with(mcp_config, timeout=30)
        mock_condenser_from_spec.assert_called_once_with(condenser_spec)


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
