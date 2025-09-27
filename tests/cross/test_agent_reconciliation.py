"""Test agent reconciliation logic in agent deserialization and conversation restart."""

import tempfile
import uuid
from unittest.mock import patch

from pydantic import SecretStr

from openhands.sdk import Agent, LocalFileStore
from openhands.sdk.agent import AgentBase
from openhands.sdk.context.condenser.llm_summarizing_condenser import (
    LLMSummarizingCondenser,
)
from openhands.sdk.conversation import Conversation
from openhands.sdk.conversation.impl.local_conversation import LocalConversation
from openhands.sdk.llm import LLM, Message, TextContent
from openhands.sdk.preset.default import get_default_agent
from openhands.sdk.tool import ToolSpec, register_tool
from openhands.tools.execute_bash import BashTool
from openhands.tools.str_replace_editor import FileEditorTool


register_tool("BashTool", BashTool)
register_tool("FileEditorTool", FileEditorTool)


# Tests from test_llm_reconciliation.py
def test_conversation_restart_with_nested_llms(tmp_path):
    """Test conversation restart with agent containing nested LLMs."""
    # Create a default agent with dummy LLM + models + keys

    working_dir = str(tmp_path)

    llm = LLM(
        model="gpt-4o-mini", api_key=SecretStr("llm-api-key"), service_id="main-llm"
    )

    # Use the standard Agent class to avoid polymorphic deserialization issues
    agent = get_default_agent(llm, working_dir)

    # Create a file store for the conversation
    file_store = LocalFileStore(root=working_dir)
    conversation_id = uuid.uuid4()

    # Create a conversation with the default agent + file store
    conversation1 = Conversation(
        agent=agent,
        persist_filestore=file_store,
        conversation_id=conversation_id,
    )

    # Verify the conversation was created successfully
    assert conversation1.id == conversation_id
    assert conversation1.agent.llm.api_key is not None
    assert conversation1.agent.llm.api_key.get_secret_value() == "llm-api-key"
    assert isinstance(conversation1.agent.condenser, LLMSummarizingCondenser)
    assert conversation1.agent.condenser.llm.api_key is not None
    assert conversation1.agent.condenser.llm.api_key.get_secret_value() == "llm-api-key"

    # Attempt to restart the conversation - this should work without errors
    conversation2 = Conversation(
        agent=agent,
        persist_filestore=file_store,
        conversation_id=conversation_id,  # Same conversation_id
    )

    # Make sure the conversation gets initialized properly with no errors
    assert conversation2.id == conversation_id
    assert conversation2.agent.llm.api_key is not None
    assert conversation2.agent.llm.api_key.get_secret_value() == "llm-api-key"
    assert isinstance(conversation2.agent.condenser, LLMSummarizingCondenser)
    assert conversation2.agent.condenser.llm.api_key is not None
    assert conversation2.agent.condenser.llm.api_key.get_secret_value() == "llm-api-key"

    # Verify that the agent configuration is properly reconciled
    assert conversation2.agent.llm.model == "gpt-4o-mini"
    assert conversation2.agent.condenser.llm.model == "gpt-4o-mini"
    assert conversation2.agent.condenser.max_size == 80
    assert conversation2.agent.condenser.keep_first == 4


def test_conversation_restarted_with_changed_working_directory(tmp_path_factory):
    working_dir = str(tmp_path_factory.mktemp("persist"))
    path1 = str(tmp_path_factory.mktemp("agent1"))
    path2 = str(tmp_path_factory.mktemp("agent2"))

    llm = LLM(
        model="gpt-4o-mini", api_key=SecretStr("llm-api-key"), service_id="main-llm"
    )

    agent1 = get_default_agent(llm, str(path1))
    file_store = LocalFileStore(root=str(working_dir))
    conversation_id = uuid.uuid4()

    # first conversation
    _ = Conversation(
        agent=agent1, persist_filestore=file_store, conversation_id=conversation_id
    )

    # agent built in a *different* temp dir
    agent2 = get_default_agent(llm, str(path2))

    # restart with new agent working dir but same conversation id
    _ = Conversation(
        agent=agent2, persist_filestore=file_store, conversation_id=conversation_id
    )


# Tests from test_local_conversation_tools_integration.py
def test_conversation_with_different_agent_tools_succeeds():
    """Test that using an agent with different tools succeeds (tools are overridden)."""
    with tempfile.TemporaryDirectory() as temp_dir:
        file_store = LocalFileStore(temp_dir)

        # Create and save conversation with original agent
        original_tools = [
            ToolSpec(name="BashTool", params={"working_dir": temp_dir}),
            ToolSpec(name="FileEditorTool"),
        ]
        llm = LLM(
            model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="test-llm"
        )
        original_agent = Agent(llm=llm, tools=original_tools)
        conversation = LocalConversation(
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

        # Try to create new conversation with different tools (only bash tool)
        different_tools = [
            ToolSpec(name="BashTool", params={"working_dir": temp_dir})
        ]  # Missing FileEditorTool
        llm2 = LLM(
            model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="test-llm"
        )
        different_agent = Agent(llm=llm2, tools=different_tools)

        # This should succeed - tools are overridden from runtime agent
        new_conversation = LocalConversation(
            agent=different_agent,
            persist_filestore=file_store,
            conversation_id=conversation_id,  # Use same ID to avoid ID mismatch
            visualize=False,
        )

        # Verify state was loaded and tools were overridden
        assert len(new_conversation.state.events) > 0
        # The agent should now have the runtime agent's tools (only BashTool)
        assert len(new_conversation.agent.tools) == 1
        assert new_conversation.agent.tools[0].name == "BashTool"


def test_conversation_with_same_agent_succeeds():
    """Test that using the same agent configuration succeeds."""
    with tempfile.TemporaryDirectory() as temp_dir:
        file_store = LocalFileStore(temp_dir)

        # Create and save conversation
        tools = [
            ToolSpec(name="BashTool", params={"working_dir": temp_dir}),
            ToolSpec(name="FileEditorTool"),
        ]
        llm = LLM(
            model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="test-llm"
        )
        original_agent = Agent(llm=llm, tools=tools)
        conversation = LocalConversation(
            agent=original_agent, persist_filestore=file_store, visualize=False
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
            ToolSpec(name="BashTool", params={"working_dir": temp_dir}),
            ToolSpec(name="FileEditorTool"),
        ]
        llm2 = LLM(
            model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="test-llm"
        )
        same_agent = Agent(llm=llm2, tools=same_tools)

        # This should succeed
        new_conversation = LocalConversation(
            agent=same_agent,
            persist_filestore=file_store,
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
        file_store = LocalFileStore(temp_dir)
        tools = [
            ToolSpec(name="BashTool", params={"working_dir": temp_dir}),
            ToolSpec(name="FileEditorTool"),
        ]
        llm = LLM(
            model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="test-llm"
        )
        agent = Agent(llm=llm, tools=tools)

        # Create conversation and send messages
        conversation = LocalConversation(
            agent=agent, persist_filestore=file_store, visualize=False
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
            persist_filestore=file_store,
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
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create original agent
        tools = [ToolSpec(name="BashTool", params={"working_dir": temp_dir})]
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
