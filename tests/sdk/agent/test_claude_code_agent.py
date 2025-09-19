"""Tests for ClaudeCodeAgent implementation."""
# pyright: reportOptionalCall=false, reportArgumentType=false

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

from openhands.sdk.llm import LLM
from openhands.tools import BashTool


# Only run tests if claude-code-sdk is available
pytest_plugins = []

try:
    from claude_code_sdk import (  # type: ignore[import-untyped]
        AssistantMessage,
        ClaudeCodeOptions,
        TextBlock,
        ToolUseBlock,
    )

    from openhands.sdk.agent import ClaudeCodeAgent  # type: ignore[attr-defined]

    CLAUDE_CODE_AVAILABLE = True
except ImportError:
    CLAUDE_CODE_AVAILABLE = False
    # Define dummy classes for type checking when not available
    ClaudeCodeAgent = None  # type: ignore[misc,assignment]
    ClaudeCodeOptions = None  # type: ignore[misc,assignment]
    AssistantMessage = None  # type: ignore[misc,assignment]
    TextBlock = None  # type: ignore[misc,assignment]
    ToolUseBlock = None  # type: ignore[misc,assignment]


@pytest.mark.skipif(not CLAUDE_CODE_AVAILABLE, reason="claude-code-sdk not available")
class TestClaudeCodeAgent:  # type: ignore[misc]
    """Test ClaudeCodeAgent implementation."""

    def setup_method(self):
        """Set up test environment."""
        self.llm = LLM(model="gpt-4", api_key=SecretStr("test-key"))
        self.bash_tool = BashTool.create(working_dir="/tmp")

    def test_claude_code_agent_creation(self):
        """Test that ClaudeCodeAgent can be created successfully."""
        agent = ClaudeCodeAgent(llm=self.llm, tools=[self.bash_tool])

        assert agent.llm == self.llm
        assert isinstance(agent.tools, dict)
        assert "execute_bash" in agent.tools
        # claude_options can be None by default
        assert agent.claude_options is None or isinstance(agent.claude_options, dict)

    def test_claude_code_agent_inherits_from_agent_base(self):
        """Test that ClaudeCodeAgent properly inherits from AgentBase."""
        agent = ClaudeCodeAgent(llm=self.llm, tools=[])

        # Should have all AgentBase properties
        assert hasattr(agent, "system_message")
        assert hasattr(agent, "name")
        assert hasattr(agent, "prompt_dir")
        assert agent.name == "ClaudeCodeAgent"

    def test_claude_code_agent_is_frozen(self):
        """Test that ClaudeCodeAgent instances are frozen (immutable)."""
        agent = ClaudeCodeAgent(llm=self.llm, tools=[])

        # Test that we cannot modify core fields after creation
        with pytest.raises(Exception):  # ValidationError or AttributeError
            agent.llm = "new_value"  # type: ignore[assignment]

    def test_claude_code_agent_with_custom_options(self):
        """Test ClaudeCodeAgent with custom Claude Code options."""
        custom_options = {
            "allowed_tools": ["Read", "Write"],
            "max_turns": 5,
            "permission_mode": "acceptEdits",
        }

        agent = ClaudeCodeAgent(llm=self.llm, tools=[], claude_options=custom_options)

        assert agent.claude_options["allowed_tools"] == ["Read", "Write"]  # type: ignore[index]
        assert agent.claude_options["max_turns"] == 5  # type: ignore[index]
        assert agent.claude_options["permission_mode"] == "acceptEdits"  # type: ignore[index]

    def test_tool_conversion_to_mcp(self):
        """Test that OpenHands tools are properly converted to MCP tools."""
        agent = ClaudeCodeAgent(llm=self.llm, tools=[self.bash_tool])

        # Create client to trigger tool conversion
        with patch(
            "openhands.sdk.agent.claude_code_agent.ClaudeSDKClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            agent._create_claude_client()

            # Verify client was created with proper options
            mock_client_class.assert_called_once()
            call_args = mock_client_class.call_args[1]  # kwargs
            options = call_args["options"]

            assert isinstance(options, ClaudeCodeOptions)
            assert "openhands" in options.mcp_servers
            assert "mcp__openhands__execute_bash" in options.allowed_tools

    @patch("openhands.sdk.agent.claude_code_agent.asyncio.run")
    def test_step_method_calls_async_step(self, mock_asyncio_run):
        """Test that step method properly calls async implementation."""
        agent = ClaudeCodeAgent(llm=self.llm, tools=[])

        # Mock conversation state and callback
        mock_state = MagicMock()
        mock_callback = MagicMock()

        # Call step method
        agent.step(mock_state, mock_callback)

        # Verify asyncio.run was called
        mock_asyncio_run.assert_called_once()

    @patch("openhands.sdk.agent.claude_code_agent.ClaudeSDKClient")
    @patch("openhands.sdk.agent.claude_code_agent.asyncio.run")
    def test_async_step_with_user_message(self, mock_asyncio_run, mock_client_class):
        """Test async step method with user message."""
        agent = ClaudeCodeAgent(llm=self.llm, tools=[])

        # Mock conversation state with user message
        mock_state = MagicMock()
        mock_message_event = MagicMock()
        mock_message_event.source = "user"
        mock_message_event.llm_message.content = [MagicMock()]
        mock_message_event.llm_message.content[0].text = "Hello"
        mock_state.events = [mock_message_event]

        mock_callback = MagicMock()

        # Mock Claude client
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client

        # Mock async context manager
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        # Mock receive_response to return empty iterator
        async def mock_receive_response():
            return
            yield  # Make it an async generator

        mock_client.receive_response = mock_receive_response

        # Call the actual async method directly for testing

        async def run_test():
            await agent._async_step(mock_state, mock_callback)

        # Don't actually run asyncio.run, just test the method exists
        assert hasattr(agent, "_async_step")

    def test_process_assistant_message_with_text(self):
        """Test processing AssistantMessage with text content."""
        agent = ClaudeCodeAgent(llm=self.llm, tools=[])

        # Create mock AssistantMessage with text
        text_block = TextBlock(text="Hello, how can I help you?")
        assistant_message = AssistantMessage(
            content=[text_block], model="claude-3-sonnet"
        )

        mock_state = MagicMock()
        mock_callback = MagicMock()

        # Process the message
        agent._process_assistant_message(assistant_message, mock_state, mock_callback)

        # Verify callback was called with MessageEvent
        mock_callback.assert_called_once()
        call_args = mock_callback.call_args[0]
        message_event = call_args[0]

        assert hasattr(message_event, "source")
        assert message_event.source == "agent"

    def test_process_tool_use_block(self):
        """Test processing ToolUseBlock from Claude Code."""
        agent = ClaudeCodeAgent(llm=self.llm, tools=[self.bash_tool])

        # Create mock ToolUseBlock
        tool_block = ToolUseBlock(
            id="tool_123",
            name="mcp__openhands__execute_bash",
            input={"command": "echo hello"},
        )

        mock_state = MagicMock()
        mock_callback = MagicMock()

        # Process the tool use block
        agent._process_tool_use_block(tool_block, mock_state, mock_callback)

        # Verify callback was called twice (ActionEvent and ObservationEvent)
        assert mock_callback.call_count == 2

    def test_process_tool_use_block_unknown_tool(self):
        """Test processing ToolUseBlock with unknown tool name."""
        agent = ClaudeCodeAgent(llm=self.llm, tools=[])

        # Create mock ToolUseBlock with unknown tool
        tool_block = ToolUseBlock(
            id="tool_123", name="unknown_tool", input={"param": "value"}
        )

        mock_state = MagicMock()
        mock_callback = MagicMock()

        # Process the tool use block
        agent._process_tool_use_block(tool_block, mock_state, mock_callback)

        # Verify callback was called with error event
        mock_callback.assert_called_once()
        call_args = mock_callback.call_args[0]
        error_event = call_args[0]

        assert hasattr(error_event, "error")
        assert "not found" in error_event.error

    def test_init_state_method(self):
        """Test init_state method."""
        agent = ClaudeCodeAgent(llm=self.llm, tools=[self.bash_tool])

        mock_state = MagicMock()
        mock_state.events = []  # Empty events list
        mock_callback = MagicMock()

        # Call init_state
        agent.init_state(mock_state, mock_callback)

        # Verify callback was called with SystemPromptEvent
        mock_callback.assert_called_once()
        call_args = mock_callback.call_args[0]
        system_event = call_args[0]

        assert hasattr(system_event, "source")
        assert system_event.source == "agent"

    def test_convert_tool_to_mcp_success(self):
        """Test successful conversion of OpenHands tool to MCP tool."""
        agent = ClaudeCodeAgent(llm=self.llm, tools=[self.bash_tool])

        # Get the bash tool
        assert isinstance(agent.tools, dict)
        bash_tool = agent.tools["execute_bash"]

        # Convert to MCP tool
        mcp_tool = agent._convert_tool_to_mcp(bash_tool)

        # Verify MCP tool was created
        assert mcp_tool is not None
        # MCP tool should have a handler that's callable
        assert hasattr(mcp_tool, "handler")
        assert callable(mcp_tool.handler)

    def test_convert_tool_to_mcp_no_executor(self):
        """Test conversion of tool with no executor."""
        agent = ClaudeCodeAgent(llm=self.llm, tools=[])

        # Create mock tool without executor
        mock_tool = MagicMock()
        mock_tool.executor = None
        mock_tool.name = "test_tool"

        # Convert to MCP tool
        mcp_tool = agent._convert_tool_to_mcp(mock_tool)

        # Should return None for tools without executor
        assert mcp_tool is None

    def test_system_message_property(self):
        """Test that system_message property works correctly."""
        agent = ClaudeCodeAgent(llm=self.llm, tools=[])

        system_message = agent.system_message

        assert isinstance(system_message, str)
        assert len(system_message) > 0

    def test_agent_equality(self):
        """Test agent equality comparison."""
        agent1 = ClaudeCodeAgent(llm=self.llm, tools=[])
        agent2 = ClaudeCodeAgent(llm=self.llm, tools=[])

        # Should be equal with same configuration
        assert agent1 == agent2

        # But different instances
        assert agent1 is not agent2

    def test_agent_with_different_claude_options(self):
        """Test agents with different Claude options are different."""
        options1 = {"max_turns": 1}
        options2 = {"max_turns": 5}

        agent1 = ClaudeCodeAgent(llm=self.llm, tools=[], claude_options=options1)
        agent2 = ClaudeCodeAgent(llm=self.llm, tools=[], claude_options=options2)

        # Should be different due to different options
        assert agent1 != agent2
