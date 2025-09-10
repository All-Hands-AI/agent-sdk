"""Test ConversationState serialization and persistence logic."""

import json
import tempfile
from pathlib import Path

import pytest
from pydantic import SecretStr

from openhands.sdk import Agent, Conversation, LocalFileStore
from openhands.sdk.agent.base import AgentBase
from openhands.sdk.conversation.state import ConversationState
from openhands.sdk.conversation.types import ConversationCallbackType
from openhands.sdk.event.llm_convertible import MessageEvent, SystemPromptEvent
from openhands.sdk.llm import LLM, Message, TextContent
from openhands.tools import BashTool, FileEditorTool


class TestAgent(AgentBase):
    """Test agent for serialization tests."""

    def __init__(self, llm=None, tools=None, **kwargs):
        if llm is None:
            llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"))
        super().__init__(llm=llm, tools=tools or [], **kwargs)

    def init_state(
        self, state: ConversationState, on_event: ConversationCallbackType
    ) -> None:
        event = SystemPromptEvent(
            source="agent",
            system_prompt=TextContent(text="test system prompt"),
            tools=[],
        )
        on_event(event)

    def step(
        self, state: ConversationState, on_event: ConversationCallbackType
    ) -> None:
        on_event(
            MessageEvent(
                source="agent",
                llm_message=Message(
                    role="assistant", content=[TextContent(text="test response")]
                ),
            )
        )
        state.agent_finished = True


def test_conversation_state_basic_serialization():
    """Test basic ConversationState serialization and deserialization."""
    agent = TestAgent()
    state = ConversationState(agent=agent)

    # Add some events
    event1 = SystemPromptEvent(
        source="agent", system_prompt=TextContent(text="system"), tools=[]
    )
    event2 = MessageEvent(
        source="user",
        llm_message=Message(role="user", content=[TextContent(text="hello")]),
    )
    state.events = [event1, event2]

    # Test serialization
    serialized = state.model_dump_json(exclude_none=True)
    assert isinstance(serialized, str)

    # Test deserialization
    deserialized = ConversationState.model_validate_json(serialized)
    assert deserialized.id == state.id
    assert len(deserialized.events) == 2
    assert isinstance(deserialized.events[0], SystemPromptEvent)
    assert isinstance(deserialized.events[1], MessageEvent)
    # Compare key fields instead of full model dump due to minor serialization
    # differences
    assert deserialized.agent.llm.model == agent.llm.model
    assert deserialized.agent.__class__ == agent.__class__


def test_conversation_state_persistence_save_load():
    """Test ConversationState save and load with FileStore."""
    with tempfile.TemporaryDirectory() as temp_dir:
        file_store = LocalFileStore(temp_dir)
        agent = TestAgent()
        state = ConversationState(agent=agent)

        # Add events
        event1 = SystemPromptEvent(
            source="agent", system_prompt=TextContent(text="system"), tools=[]
        )
        event2 = MessageEvent(
            source="user",
            llm_message=Message(role="user", content=[TextContent(text="hello")]),
        )
        state.events = [event1, event2]

        # Save state
        state.save(file_store)

        # Verify files were created
        assert Path(temp_dir, "base_state.json").exists()
        assert Path(temp_dir, "events", "event-00000.json").exists()
        assert Path(temp_dir, "events", "event-00001.json").exists()

        # Load state
        loaded_state = ConversationState.load(file_store)

        # Verify loaded state matches original
        assert loaded_state.id == state.id
        assert len(loaded_state.events) == 2
        assert isinstance(loaded_state.events[0], SystemPromptEvent)
        assert isinstance(loaded_state.events[1], MessageEvent)
        assert loaded_state.agent.llm.model == agent.llm.model
        assert loaded_state.agent.__class__ == agent.__class__


def test_conversation_state_incremental_save():
    """Test that ConversationState saves only new events incrementally."""
    with tempfile.TemporaryDirectory() as temp_dir:
        file_store = LocalFileStore(temp_dir)
        agent = TestAgent()
        state = ConversationState(agent=agent)

        # Add first event and save
        event1 = SystemPromptEvent(
            source="agent", system_prompt=TextContent(text="system"), tools=[]
        )
        state.events = [event1]
        state.save(file_store)

        # Verify only one event file exists
        event_files = list(Path(temp_dir, "events").glob("*.json"))
        assert len(event_files) == 1

        # Add second event and save again
        event2 = MessageEvent(
            source="user",
            llm_message=Message(role="user", content=[TextContent(text="hello")]),
        )
        state.events.append(event2)
        state.save(file_store)

        # Verify two event files exist now
        event_files = list(Path(temp_dir, "events").glob("*.json"))
        assert len(event_files) == 2

        # Load and verify both events are present
        loaded_state = ConversationState.load(file_store)
        assert len(loaded_state.events) == 2


def test_conversation_state_event_file_scanning():
    """Test event file scanning and sorting logic."""
    with tempfile.TemporaryDirectory() as temp_dir:
        file_store = LocalFileStore(temp_dir)

        # Create event files out of order
        events_dir = Path(temp_dir, "events")
        events_dir.mkdir()

        # Create files with different indices
        (events_dir / "event-00002.json").write_text('{"type": "test", "id": "3"}')
        (events_dir / "event-00000.json").write_text('{"type": "test", "id": "1"}')
        (events_dir / "event-00001.json").write_text('{"type": "test", "id": "2"}')
        (events_dir / "invalid-file.json").write_text('{"type": "test"}')

        # Test scanning
        event_files = ConversationState._scan_events(file_store)

        # Should be sorted by index and exclude invalid files
        assert len(event_files) == 3
        assert event_files[0].idx == 0
        assert event_files[1].idx == 1
        assert event_files[2].idx == 2


def test_conversation_state_corrupted_event_handling():
    """Test handling of corrupted event files during replay."""
    with tempfile.TemporaryDirectory() as temp_dir:
        file_store = LocalFileStore(temp_dir)

        # Create event files with some corrupted
        events_dir = Path(temp_dir, "events")
        events_dir.mkdir()

        # Valid event
        valid_event = SystemPromptEvent(
            source="agent", system_prompt=TextContent(text="system"), tools=[]
        )
        (events_dir / "event-00000.json").write_text(
            valid_event.model_dump_json(exclude_none=True)
        )

        # Corrupted JSON
        (events_dir / "event-00001.json").write_text('{"invalid": json}')

        # Empty file
        (events_dir / "event-00002.json").write_text("")

        # Valid event
        valid_event2 = MessageEvent(
            source="user",
            llm_message=Message(role="user", content=[TextContent(text="hello")]),
        )
        (events_dir / "event-00003.json").write_text(
            valid_event2.model_dump_json(exclude_none=True)
        )

        # Test replay - should skip corrupted files
        event_files = ConversationState._scan_events(file_store)
        events = ConversationState._replay_from_files(file_store, event_files)

        # Should only have valid events
        assert len(events) == 2
        assert isinstance(events[0], SystemPromptEvent)
        assert isinstance(events[1], MessageEvent)


def test_conversation_with_different_agent_tools_raises_error():
    """Test that using an agent with different tools raises ValueError."""
    with tempfile.TemporaryDirectory() as temp_dir:
        file_store = LocalFileStore(temp_dir)

        # Create and save conversation with original agent
        original_tools = [
            BashTool.create(working_dir=temp_dir),
            FileEditorTool.create(),
        ]
        original_agent = TestAgent(tools=original_tools)
        conversation = Conversation(
            agent=original_agent, persist_filestore=file_store, visualize=False
        )

        # Send a message to create some state
        conversation.send_message(
            Message(role="user", content=[TextContent(text="test message")])
        )

        # Delete conversation to simulate restart
        del conversation

        # Try to create new conversation with different tools (only bash tool)
        different_tools = [
            BashTool.create(working_dir=temp_dir)
        ]  # Missing FileEditorTool
        different_agent = TestAgent(tools=different_tools)

        # This should raise ValueError due to tool differences
        with pytest.raises(
            ValueError, match="different from the one in persisted state"
        ):
            Conversation(
                agent=different_agent, persist_filestore=file_store, visualize=False
            )


def test_conversation_with_same_agent_succeeds():
    """Test that using the same agent configuration succeeds."""
    with tempfile.TemporaryDirectory() as temp_dir:
        file_store = LocalFileStore(temp_dir)

        # Create and save conversation
        tools = [BashTool.create(working_dir=temp_dir), FileEditorTool.create()]
        original_agent = TestAgent(tools=tools)
        conversation = Conversation(
            agent=original_agent, persist_filestore=file_store, visualize=False
        )

        # Send a message
        conversation.send_message(
            Message(role="user", content=[TextContent(text="test message")])
        )

        # Delete conversation
        del conversation

        # Create new conversation with same agent configuration
        same_tools = [BashTool.create(working_dir=temp_dir), FileEditorTool.create()]
        same_agent = TestAgent(tools=same_tools)

        # This should succeed
        new_conversation = Conversation(
            agent=same_agent, persist_filestore=file_store, visualize=False
        )

        # Verify state was loaded
        assert len(new_conversation.state.events) > 0


def test_conversation_persistence_lifecycle():
    """Test full conversation persistence lifecycle similar to examples/10_persistence.py."""  # noqa: E501
    with tempfile.TemporaryDirectory() as temp_dir:
        file_store = LocalFileStore(temp_dir)
        tools = [BashTool.create(working_dir=temp_dir), FileEditorTool.create()]
        agent = TestAgent(tools=tools)

        # Create conversation and send messages
        conversation = Conversation(
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

        # Delete conversation to simulate restart
        del conversation

        # Create new conversation (should load from persistence)
        new_conversation = Conversation(
            agent=agent, persist_filestore=file_store, visualize=False
        )

        # Verify state was restored
        assert new_conversation.id == original_id
        # Note: When loading from persistence, init_state() is still called which
        # adds a system prompt. So we expect one additional event
        assert len(new_conversation.state.events) == original_event_count + 1

        # Send another message to verify conversation continues
        new_conversation.send_message(
            Message(role="user", content=[TextContent(text="Third message")])
        )
        new_conversation.run()

        # Verify new event was added
        # We expect: original_event_count + 1 (system prompt from init) + 2
        # (user message + agent response)
        assert len(new_conversation.state.events) >= original_event_count + 2


def test_conversation_state_empty_filestore():
    """Test ConversationState behavior with empty filestore."""
    with tempfile.TemporaryDirectory() as temp_dir:
        file_store = LocalFileStore(temp_dir)
        agent = TestAgent()

        # Create conversation with empty filestore
        conversation = Conversation(
            agent=agent, persist_filestore=file_store, visualize=False
        )

        # Should create new state
        assert conversation.state.id is not None
        assert len(conversation.state.events) == 1  # System prompt event
        assert isinstance(conversation.state.events[0], SystemPromptEvent)


def test_conversation_state_missing_base_state():
    """Test error handling when base_state.json is missing but events exist."""
    with tempfile.TemporaryDirectory() as temp_dir:
        file_store = LocalFileStore(temp_dir)

        # Create events directory with files but no base_state.json
        events_dir = Path(temp_dir, "events")
        events_dir.mkdir()
        event = SystemPromptEvent(
            source="agent", system_prompt=TextContent(text="system"), tools=[]
        )
        (events_dir / "event-00000.json").write_text(
            event.model_dump_json(exclude_none=True)
        )

        # Should raise error when trying to load
        with pytest.raises(Exception):  # Could be FileNotFoundError or similar
            ConversationState.load(file_store)


def test_conversation_state_exclude_from_base_state():
    """Test that events are excluded from base state serialization."""
    with tempfile.TemporaryDirectory() as temp_dir:
        file_store = LocalFileStore(temp_dir)
        agent = TestAgent()
        state = ConversationState(agent=agent)

        # Add events
        event = SystemPromptEvent(
            source="agent", system_prompt=TextContent(text="system"), tools=[]
        )
        state.events = [event]

        # Save state
        state.save(file_store)

        # Read base state file directly
        base_state_content = file_store.read("base_state.json")
        base_state_data = json.loads(base_state_content)

        # Events should not be in base state
        assert "events" not in base_state_data
        assert "agent" in base_state_data
        assert "id" in base_state_data


def test_conversation_state_thread_safety():
    """Test ConversationState thread safety with lock/unlock."""
    agent = TestAgent()
    state = ConversationState(agent=agent)

    # Test context manager
    with state:
        state.assert_locked()
        # Should not raise error when locked by current thread

    # Test manual acquire/release
    state.acquire()
    try:
        state.assert_locked()
    finally:
        state.release()

    # Test error when not locked
    with pytest.raises(RuntimeError, match="State not held by current thread"):
        state.assert_locked()


def test_agent_resolve_diff_from_deserialized():
    """Test agent's resolve_diff_from_deserialized method."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create original agent
        tools = [BashTool.create(working_dir=temp_dir)]
        original_agent = TestAgent(tools=tools)

        # Serialize and deserialize to simulate persistence
        serialized = original_agent.model_dump_json()
        deserialized_agent = TestAgent.model_validate_json(serialized)

        # Create runtime agent with same configuration
        runtime_agent = TestAgent(tools=tools)

        # Should resolve successfully
        resolved = runtime_agent.resolve_diff_from_deserialized(deserialized_agent)
        assert resolved.llm.model == runtime_agent.llm.model
        assert resolved.__class__ == runtime_agent.__class__


def test_agent_resolve_diff_different_class_raises_error():
    """Test that resolve_diff_from_deserialized raises error for different agent classes."""  # noqa: E501

    class DifferentAgent(AgentBase):
        def __init__(self):
            llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"))
            super().__init__(llm=llm, tools=[])

        def init_state(self, state, on_event):
            pass

        def step(self, state, on_event):
            pass

    original_agent = TestAgent()
    different_agent = DifferentAgent()

    with pytest.raises(ValueError, match="Cannot resolve from deserialized"):
        original_agent.resolve_diff_from_deserialized(different_agent)


def test_conversation_state_flags_persistence():
    """Test that conversation state flags are properly persisted."""
    with tempfile.TemporaryDirectory() as temp_dir:
        file_store = LocalFileStore(temp_dir)
        agent = TestAgent()
        state = ConversationState(agent=agent)

        # Set various flags
        state.agent_finished = True
        state.confirmation_mode = True
        state.agent_waiting_for_confirmation = True
        state.agent_paused = True
        state.activated_knowledge_microagents = ["agent1", "agent2"]

        # Save and load
        state.save(file_store)
        loaded_state = ConversationState.load(file_store)

        # Verify flags are preserved
        assert loaded_state.agent_finished is True
        assert loaded_state.confirmation_mode is True
        assert loaded_state.agent_waiting_for_confirmation is True
        assert loaded_state.agent_paused is True
        assert loaded_state.activated_knowledge_microagents == ["agent1", "agent2"]


def test_conversation_with_agent_different_llm_config():
    """Test conversation with agent having different LLM configuration."""
    with tempfile.TemporaryDirectory() as temp_dir:
        file_store = LocalFileStore(temp_dir)

        # Create conversation with original LLM config
        original_llm = LLM(model="gpt-4o-mini", api_key=SecretStr("original-key"))
        original_agent = Agent(llm=original_llm, tools=[])
        conversation = Conversation(
            agent=original_agent, persist_filestore=file_store, visualize=False
        )

        # Send a message
        conversation.send_message(
            Message(role="user", content=[TextContent(text="test")])
        )

        del conversation

        # Try with different LLM config (different API key should be resolved)
        new_llm = LLM(model="gpt-4o-mini", api_key=SecretStr("new-key"))
        new_agent = Agent(llm=new_llm, tools=[])

        # This should succeed because API key differences are resolved
        new_conversation = Conversation(
            agent=new_agent, persist_filestore=file_store, visualize=False
        )

        assert new_conversation.state.agent.llm.api_key is not None
        assert new_conversation.state.agent.llm.api_key.get_secret_value() == "new-key"
