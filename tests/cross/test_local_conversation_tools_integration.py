"""Test ConversationState integration with tools from openhands.tools package."""

import tempfile
from unittest.mock import patch

import pytest
from pydantic import SecretStr

from openhands.sdk import Agent
from openhands.sdk.agent import AgentBase
from openhands.sdk.conversation.impl.local_conversation import LocalConversation
from openhands.sdk.llm import LLM, Message, TextContent
from openhands.sdk.tool import ToolSpec, register_tool
from openhands.tools.execute_bash import BashTool
from openhands.tools.str_replace_editor import FileEditorTool


register_tool("BashTool", BashTool)
register_tool("FileEditorTool", FileEditorTool)


def test_conversation_with_different_agent_tools_raises_error():
    """Test that using an agent with different tools raises ValueError."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create and save conversation with original agent
        original_tools = [
            ToolSpec(name="BashTool"),
            ToolSpec(name="FileEditorTool"),
        ]
        llm = LLM(
            model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="test-llm"
        )
        original_agent = Agent(llm=llm, tools=original_tools)
        conversation = LocalConversation(
            agent=original_agent,
            workspace=temp_dir,
            persistence_dir=temp_dir,
            visualize=False,
        )

        # Send a message to create some state
        conversation.send_message(
            Message(role="user", content=[TextContent(text="test message")])
        )

        # Get the conversation ID for reuse
        conversation_id = conversation.state.id

        # Delete conversation to simulate restart
        del conversation

        # Try to create new conversation with different tools (only bash tool)
        different_tools = [ToolSpec(name="BashTool")]  # Missing FileEditorTool
        llm2 = LLM(
            model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="test-llm"
        )
        different_agent = Agent(llm=llm2, tools=different_tools)

        # This should raise ValueError due to tool differences
        with pytest.raises(
            ValueError, match="different from the one in persisted state"
        ):
            LocalConversation(
                agent=different_agent,
                workspace=temp_dir,
                persistence_dir=temp_dir,
                conversation_id=conversation_id,  # Use same ID to avoid ID mismatch
                visualize=False,
            )


def test_conversation_with_same_agent_succeeds():
    """Test that using the same agent configuration succeeds."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create and save conversation
        tools = [
            ToolSpec(name="BashTool"),
            ToolSpec(name="FileEditorTool"),
        ]
        llm = LLM(
            model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="test-llm"
        )
        original_agent = Agent(llm=llm, tools=tools)
        conversation = LocalConversation(
            agent=original_agent,
            workspace=temp_dir,
            persistence_dir=temp_dir,
            visualize=False,
        )

        # Send a message
        conversation.send_message(
            Message(role="user", content=[TextContent(text="test message")])
        )

        # Get the conversation ID for reuse
        conversation_id = conversation.state.id

        # Delete conversation
        del conversation

        # Create new conversation with same agent configuration
        same_tools = [
            ToolSpec(name="BashTool"),
            ToolSpec(name="FileEditorTool"),
        ]
        llm2 = LLM(
            model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="test-llm"
        )
        same_agent = Agent(llm=llm2, tools=same_tools)

        # This should succeed
        new_conversation = LocalConversation(
            agent=same_agent,
            workspace=temp_dir,
            persistence_dir=temp_dir,
            conversation_id=conversation_id,  # Use same ID
            visualize=False,
        )

        # Verify state was loaded
        assert len(new_conversation.state.events) > 0


@patch("openhands.sdk.llm.llm.litellm_completion")
def test_conversation_persistence_lifecycle(mock_completion):
    """Test full conversation persistence lifecycle similar to examples/10_persistence.py."""  # noqa: E501
    from tests.conftest import create_mock_litellm_response

    # Mock the LLM completion call
    mock_response = create_mock_litellm_response(
        content="I'll help you with that task.", finish_reason="stop"
    )
    mock_completion.return_value = mock_response

    with tempfile.TemporaryDirectory() as temp_dir:
        tools = [
            ToolSpec(name="BashTool"),
            ToolSpec(name="FileEditorTool"),
        ]
        llm = LLM(
            model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="test-llm"
        )
        agent = Agent(llm=llm, tools=tools)

        # Create conversation and send messages
        conversation = LocalConversation(
            agent=agent, workspace=temp_dir, persistence_dir=temp_dir, visualize=False
        )

        # Send first message
        conversation.send_message(
            Message(role="user", content=[TextContent(text="First message")])
        )
        conversation.run()

        # Send second message
        conversation.send_message(
            Message(role="user", content=[TextContent(text="Second message")])
        )
        conversation.run()

        # Store conversation ID and event count
        original_id = conversation.id
        original_event_count = len(conversation.state.events)
        original_state_dump = conversation._state.model_dump(
            mode="json", exclude={"events"}
        )

        # Delete conversation to simulate restart
        del conversation

        # Create new conversation (should load from persistence)
        new_conversation = LocalConversation(
            agent=agent,
            workspace=temp_dir,
            persistence_dir=temp_dir,
            conversation_id=original_id,  # Use same ID to load existing state
            visualize=False,
        )

        # Verify state was restored
        assert new_conversation.id == original_id
        # When loading from persistence, the state should be exactly the same
        assert len(new_conversation.state.events) == original_event_count
        # Test model_dump equality (excluding events which may have different timestamps)  # noqa: E501
        new_dump = new_conversation._state.model_dump(mode="json", exclude={"events"})
        assert new_dump == original_state_dump

        # Send another message to verify conversation continues
        new_conversation.send_message(
            Message(role="user", content=[TextContent(text="Third message")])
        )
        new_conversation.run()

        # Verify new event was added
        # We expect: original_event_count + 1 (system prompt from init) + 2
        # (user message + agent response)
        assert len(new_conversation.state.events) >= original_event_count + 2


def test_agent_resolve_diff_from_deserialized():
    """Test agent's resolve_diff_from_deserialized method."""
    with tempfile.TemporaryDirectory():
        # Create original agent
        tools = [ToolSpec(name="BashTool")]
        llm = LLM(
            model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="test-llm"
        )
        original_agent = Agent(llm=llm, tools=tools)

        # Serialize and deserialize to simulate persistence
        serialized = original_agent.model_dump_json()
        deserialized_agent = AgentBase.model_validate_json(serialized)

        # Create runtime agent with same configuration
        llm2 = LLM(
            model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="test-llm"
        )
        runtime_agent = Agent(llm=llm2, tools=tools)

        # Should resolve successfully
        resolved = runtime_agent.resolve_diff_from_deserialized(deserialized_agent)
        # Test model_dump equality
        assert resolved.model_dump(mode="json") == runtime_agent.model_dump(mode="json")
        assert resolved.llm.model == runtime_agent.llm.model
        assert resolved.__class__ == runtime_agent.__class__
