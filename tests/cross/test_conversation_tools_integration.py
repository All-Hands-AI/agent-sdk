"""Test ConversationState integration with tools from openhands.tools package."""

import tempfile
import uuid
from unittest.mock import patch

import pytest
from pydantic import SecretStr

from openhands.sdk import Agent, Conversation, LocalFileStore
from openhands.sdk.conversation.state import ConversationState
from openhands.sdk.llm import LLM, Message, TextContent
from openhands.sdk.tool import ToolSpec, register_tool
from openhands.tools.execute_bash import BashTool
from openhands.tools.str_replace_editor import FileEditorTool


register_tool("BashTool", BashTool)
register_tool("FileEditorTool", FileEditorTool)


def test_conversation_with_different_agent_tools_raises_error():
    """Test that using an agent with different tools raises ValueError."""
    with tempfile.TemporaryDirectory() as temp_dir:
        file_store = LocalFileStore(temp_dir)

        # Create and save conversation with original agent
        original_tools = [
            ToolSpec(name="BashTool", params={"working_dir": temp_dir}),
            ToolSpec(name="FileEditorTool"),
        ]
        llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"))
        original_agent = Agent(llm=llm, tools=original_tools)
        conversation = Conversation(
            agent=original_agent, persist_filestore=file_store, visualize=False
        )

        # Send a message to create some state
        conversation.send_message(
            Message(role="user", content=[TextContent(text="test message")])
        )

        # Get the conversation ID for reuse
        conversation_id = conversation.state.id

        # Delete conversation to simulate restart
        del conversation

        # Try to load with agent that has different tools
        different_tools = [
            ToolSpec(name="BashTool", params={"working_dir": temp_dir})
        ]  # Missing FileEditorTool
        different_agent = Agent(llm=llm, tools=different_tools)

        # This should raise ValueError due to tool mismatch
        with pytest.raises(
            ValueError,
            match="The Agent provided is different from the one in persisted state",
        ):
            Conversation(
                agent=different_agent,
                persist_filestore=file_store,
                conversation_id=conversation_id,
                visualize=False,
            )


def test_conversation_with_same_agent_succeeds():
    """Test that using an agent with same tools succeeds."""
    with tempfile.TemporaryDirectory() as temp_dir:
        file_store = LocalFileStore(temp_dir)

        # Create and save conversation with original agent
        original_tools = [
            ToolSpec(name="BashTool", params={"working_dir": temp_dir}),
            ToolSpec(name="FileEditorTool"),
        ]
        llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"))
        original_agent = Agent(llm=llm, tools=original_tools)
        conversation = Conversation(
            agent=original_agent, persist_filestore=file_store, visualize=False
        )

        # Send a message to create some state
        conversation.send_message(
            Message(role="user", content=[TextContent(text="test message")])
        )

        # Get the conversation ID for reuse
        conversation_id = conversation.state.id

        # Delete conversation to simulate restart
        del conversation

        # Load with agent that has same tools - should succeed
        same_agent = Agent(llm=llm, tools=original_tools)
        reloaded_conversation = Conversation(
            agent=same_agent,
            persist_filestore=file_store,
            conversation_id=conversation_id,
            visualize=False,
        )

        # Should have the same state
        assert reloaded_conversation.state.id == conversation_id
        assert len(reloaded_conversation.state.events) > 0


@patch("openhands.sdk.llm.llm.LLM.completion")
def test_conversation_persistence_lifecycle(mock_completion):
    """Test complete conversation persistence lifecycle with tools."""
    # Mock the LLM completion
    mock_completion.return_value = Message(
        role="assistant", content=[TextContent(text="Hello! I'm ready to help.")]
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        file_store = LocalFileStore(temp_dir)

        # Create conversation with tools
        tools = [
            ToolSpec(name="BashTool", params={"working_dir": temp_dir}),
            ToolSpec(name="FileEditorTool"),
        ]
        llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"))
        agent = Agent(llm=llm, tools=tools)

        # Create conversation
        conversation = Conversation(
            agent=agent, persist_filestore=file_store, visualize=False
        )
        original_id = conversation.state.id

        # Send multiple messages
        conversation.send_message(
            Message(role="user", content=[TextContent(text="First message")])
        )
        conversation.send_message(
            Message(role="user", content=[TextContent(text="Second message")])
        )

        # Verify events were created
        assert (
            len(conversation.state.events) >= 3
        )  # system + 2 user (assistant may not respond)

        # Delete conversation
        del conversation

        # Reload conversation
        reloaded_conversation = Conversation(
            agent=agent,
            persist_filestore=file_store,
            conversation_id=original_id,
            visualize=False,
        )

        # Verify state was preserved
        assert reloaded_conversation.state.id == original_id
        assert len(reloaded_conversation.state.events) >= 3

        # Send another message
        reloaded_conversation.send_message(
            Message(role="user", content=[TextContent(text="Third message")])
        )

        # Verify new events were added
        assert len(reloaded_conversation.state.events) >= 4


def test_agent_state_serialization_with_tools():
    """Test that agent state with tools can be serialized and deserialized."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create agent with tools
        tools = [ToolSpec(name="BashTool", params={"working_dir": temp_dir})]
        llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"))
        original_agent = Agent(llm=llm, tools=tools)

        # Create state
        conversation_id = uuid.uuid4()
        state = ConversationState.create(id=conversation_id, agent=original_agent)

        # Serialize and deserialize
        serialized = state.model_dump_json()
        deserialized_state = ConversationState.model_validate_json(serialized)

        # Verify the deserialized state has the same agent configuration
        assert deserialized_state.agent.tools == original_agent.tools
        assert deserialized_state.agent.llm.model == original_agent.llm.model
