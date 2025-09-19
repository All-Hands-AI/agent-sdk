"""Integration tests for ClaudeCodeAgent with Conversation."""
# pyright: reportPossiblyUnboundVariable=false, reportAttributeAccessIssue=false

from unittest.mock import AsyncMock, patch

import pytest
from pydantic import SecretStr

from openhands.sdk.conversation import Conversation
from openhands.sdk.llm import LLM, Message, TextContent
from openhands.tools import BashTool


# Only run tests if claude-code-sdk is available
try:
    from openhands.sdk.agent import ClaudeCodeAgent

    CLAUDE_CODE_AVAILABLE = True
except ImportError:
    CLAUDE_CODE_AVAILABLE = False


@pytest.mark.skipif(not CLAUDE_CODE_AVAILABLE, reason="claude-code-sdk not available")
class TestClaudeCodeAgentIntegration:
    """Test ClaudeCodeAgent integration with Conversation system."""

    def setup_method(self):
        """Set up test environment."""
        self.llm = LLM(model="gpt-4", api_key=SecretStr("test-key"))
        self.bash_tool = BashTool.create(working_dir="/tmp")

    def test_conversation_with_claude_code_agent(self):
        """Test that Conversation works with ClaudeCodeAgent."""
        agent = ClaudeCodeAgent(llm=self.llm, tools=[self.bash_tool])

        # Create conversation with the Claude Code agent
        conversation = Conversation(agent=agent, visualize=False)

        # Verify conversation was created successfully
        assert conversation.agent == agent
        assert conversation.state is not None
        assert len(conversation.state.events) > 0  # Should have system prompt

    def test_conversation_send_message_with_claude_code_agent(self):
        """Test sending messages through Conversation with ClaudeCodeAgent."""
        agent = ClaudeCodeAgent(llm=self.llm, tools=[])
        conversation = Conversation(agent=agent, visualize=False)

        # Create a user message
        user_message = Message(
            role="user", content=[TextContent(text="Hello, how are you?")]
        )

        # Send message should work without errors
        conversation.send_message(user_message)

        # Verify message was added to conversation state
        user_events = [
            event
            for event in conversation.state.events
            if hasattr(event, "source") and event.source == "user"
        ]
        assert len(user_events) == 1

    @patch("openhands.sdk.agent.claude_code_agent.ClaudeSDKClient")
    def test_conversation_run_with_claude_code_agent(self, mock_client_class):
        """Test running conversation with ClaudeCodeAgent."""
        # Mock the Claude SDK client
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        # Mock empty response
        async def mock_receive_response():
            return
            yield  # Make it an async generator

        mock_client.receive_response = mock_receive_response

        agent = ClaudeCodeAgent(llm=self.llm, tools=[])
        conversation = Conversation(agent=agent, visualize=False)

        # Send a message first
        user_message = Message(role="user", content=[TextContent(text="Hello")])
        conversation.send_message(user_message)

        # Run should complete without errors
        conversation.run()

        # Verify the agent's step method was called (indirectly through mocking)
        # The exact verification depends on the mocking setup

    def test_claude_code_agent_maintains_same_interface_as_regular_agent(self):
        """Test that ClaudeCodeAgent has the same interface as regular Agent."""
        from openhands.sdk.agent import Agent

        regular_agent = Agent(llm=self.llm, tools=[])
        claude_agent = ClaudeCodeAgent(llm=self.llm, tools=[])

        # Both should have the same core methods
        assert hasattr(claude_agent, "init_state")
        assert hasattr(claude_agent, "step")
        assert hasattr(claude_agent, "system_message")
        assert hasattr(claude_agent, "name")

        # Both should work with Conversation
        regular_conversation = Conversation(agent=regular_agent, visualize=False)
        claude_conversation = Conversation(agent=claude_agent, visualize=False)

        assert regular_conversation.agent == regular_agent
        assert claude_conversation.agent == claude_agent

    def test_claude_code_agent_with_tools_in_conversation(self):
        """Test ClaudeCodeAgent with tools in Conversation context."""
        agent = ClaudeCodeAgent(llm=self.llm, tools=[self.bash_tool])
        conversation = Conversation(agent=agent, visualize=False)

        # Verify tools are properly configured
        assert isinstance(agent.tools, dict)
        assert "execute_bash" in agent.tools

        # Verify conversation state has system prompt with tools
        system_events = [
            event
            for event in conversation.state.events
            if hasattr(event, "source")
            and event.source == "agent"
            and hasattr(event, "tools")
        ]
        assert len(system_events) > 0

        # System event should have tools information
        system_event = system_events[0]
        assert hasattr(system_event, "tools")
        assert len(system_event.tools) > 0

    def test_claude_code_agent_conversation_state_compatibility(self):
        """Test that ClaudeCodeAgent works with ConversationState."""
        agent = ClaudeCodeAgent(llm=self.llm, tools=[])
        conversation = Conversation(agent=agent, visualize=False)

        # Verify conversation state properties
        state = conversation.state
        assert hasattr(state, "events")
        assert hasattr(state, "agent_status")
        assert hasattr(state, "confirmation_mode")
        assert hasattr(state, "secrets_manager")

        # State should be properly initialized
        assert len(state.events) > 0  # Should have system prompt
        assert state.agent_status is not None

    def test_claude_code_agent_error_handling_in_conversation(self):
        """Test error handling when ClaudeCodeAgent encounters issues."""
        agent = ClaudeCodeAgent(llm=self.llm, tools=[])
        conversation = Conversation(agent=agent, visualize=False)

        # Send a message
        user_message = Message(role="user", content=[TextContent(text="Test message")])
        conversation.send_message(user_message)

        # Mock an error in the Claude SDK by patching the ClaudeSDKClient
        with patch(
            "openhands.sdk.agent.claude_code_agent.ClaudeSDKClient"
        ) as mock_client_class:
            mock_client_class.side_effect = Exception("Claude SDK error")

            # Run should handle the error gracefully
            conversation.run()

            # Check that an error event was added
            error_events = [
                event for event in conversation.state.events if hasattr(event, "error")
            ]
            assert len(error_events) > 0
            assert "Claude SDK error" in error_events[0].error

    def test_claude_code_agent_conversation_callbacks(self):
        """Test that ClaudeCodeAgent works with conversation callbacks."""
        agent = ClaudeCodeAgent(llm=self.llm, tools=[])

        # Create callback to track events
        events_received = []

        def test_callback(event):
            events_received.append(event)

        conversation = Conversation(
            agent=agent, callbacks=[test_callback], visualize=False
        )

        # Send a message
        user_message = Message(role="user", content=[TextContent(text="Test")])
        conversation.send_message(user_message)

        # Verify callbacks received events
        assert len(events_received) > 0

        # Should have received system prompt and user message events
        event_types = [type(event).__name__ for event in events_received]
        assert "SystemPromptEvent" in event_types
        assert "MessageEvent" in event_types
