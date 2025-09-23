"""Test ConversationState serialization and persistence logic."""

import json
import tempfile
import uuid
from pathlib import Path

import pytest
from pydantic import SecretStr

from openhands.sdk import Agent, Conversation, LocalFileStore
from openhands.sdk.agent.base import AgentBase
from openhands.sdk.conversation.impl.local_conversation import LocalConversation
from openhands.sdk.conversation.state import AgentExecutionStatus, ConversationState
from openhands.sdk.event.llm_convertible import MessageEvent, SystemPromptEvent
from openhands.sdk.llm import LLM, Message, TextContent
from openhands.sdk.security.confirmation_policy import AlwaysConfirm


def test_conversation_state_basic_serialization():
    """Test basic ConversationState serialization and deserialization."""
    llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"))
    agent = Agent(llm=llm, tools=[])
    state = ConversationState.create(
        agent=agent, id=uuid.UUID("12345678-1234-5678-9abc-123456789001")
    )

    # Add some events
    event1 = SystemPromptEvent(
        source="agent", system_prompt=TextContent(text="system"), tools=[]
    )
    event2 = MessageEvent(
        source="user",
        llm_message=Message(role="user", content=[TextContent(text="hello")]),
    )
    state.events.append(event1)
    state.events.append(event2)

    # Test serialization - note that events are not included in base state
    serialized = state.model_dump_json(exclude_none=True)
    assert isinstance(serialized, str)

    # Test deserialization - events won't be included in base state
    deserialized = ConversationState.model_validate_json(serialized)
    assert deserialized.id == state.id

    # Events are stored separately, so we need to check the actual events
    # through the EventLog, not through serialization
    assert len(state.events) >= 2  # May have additional events from Agent.init_state

    # Find our test events
    our_events = [
        e
        for e in state.events
        if isinstance(e, (SystemPromptEvent, MessageEvent))
        and e.source in ["agent", "user"]
    ]
    assert len(our_events) >= 2
    assert deserialized.agent.llm.model == state.agent.llm.model
    assert deserialized.agent.__class__ == state.agent.__class__

    # Verify agent properties
    assert deserialized.agent.llm.model == agent.llm.model
    assert deserialized.agent.__class__ == agent.__class__


def test_conversation_state_persistence_save_load():
    """Test ConversationState persistence with FileStore."""
    with tempfile.TemporaryDirectory() as temp_dir:
        file_store = LocalFileStore(temp_dir)
        llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"))
        agent = Agent(llm=llm, tools=[])
        state = ConversationState.create(
            agent=agent,
            id=uuid.UUID("12345678-1234-5678-9abc-123456789002"),
            file_store=file_store,
        )

        # Add events
        event1 = SystemPromptEvent(
            source="agent", system_prompt=TextContent(text="system"), tools=[]
        )
        event2 = MessageEvent(
            source="user",
            llm_message=Message(role="user", content=[TextContent(text="hello")]),
        )
        state.events.append(event1)
        state.events.append(event2)

        # State auto-saves when events are added
        # Verify files were created
        assert Path(temp_dir, "base_state.json").exists()

        # Events are stored with new naming pattern
        event_files = list(Path(temp_dir, "events").glob("*.json"))
        assert len(event_files) == 2

        # Load state using Conversation (which handles loading)
        conversation = Conversation(
            agent=agent,
            persist_filestore=file_store,
            conversation_id=uuid.UUID("12345678-1234-5678-9abc-123456789002"),
        )
        assert isinstance(conversation, LocalConversation)
        loaded_state = conversation._state

        # Verify loaded state matches original
        assert loaded_state.id == state.id
        assert len(loaded_state.events) == 2
        assert isinstance(loaded_state.events[0], SystemPromptEvent)
        assert isinstance(loaded_state.events[1], MessageEvent)
        assert loaded_state.agent.llm.model == agent.llm.model
        assert loaded_state.agent.__class__ == agent.__class__
        # Test model_dump equality
        assert loaded_state.model_dump(mode="json") == state.model_dump(mode="json")
        # Also verify key fields are preserved
        assert loaded_state.id == state.id
        assert len(loaded_state.events) == len(state.events)


def test_conversation_state_incremental_save():
    """Test that ConversationState saves events incrementally."""
    with tempfile.TemporaryDirectory() as temp_dir:
        file_store = LocalFileStore(temp_dir)
        llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"))
        agent = Agent(llm=llm, tools=[])
        state = ConversationState.create(
            agent=agent,
            id=uuid.UUID("12345678-1234-5678-9abc-123456789003"),
            file_store=file_store,
        )

        # Add first event - auto-saves
        event1 = SystemPromptEvent(
            source="agent", system_prompt=TextContent(text="system"), tools=[]
        )
        state.events.append(event1)

        # Verify event files exist (may have additional events from Agent.init_state)
        event_files = list(Path(temp_dir, "events").glob("*.json"))
        assert len(event_files) == 1

        # Add second event - auto-saves
        event2 = MessageEvent(
            source="user",
            llm_message=Message(role="user", content=[TextContent(text="hello")]),
        )
        state.events.append(event2)

        # Verify additional event file was created
        event_files = list(Path(temp_dir, "events").glob("*.json"))
        assert len(event_files) == 2

        # Load using Conversation and verify events are present
        conversation = Conversation(
            agent=agent,
            persist_filestore=file_store,
            conversation_id=uuid.UUID("12345678-1234-5678-9abc-123456789003"),
        )
        loaded_state = conversation._state
        assert len(loaded_state.events) == 2
        # Test model_dump equality
        assert loaded_state.model_dump(mode="json") == state.model_dump(mode="json")


def test_conversation_state_event_file_scanning():
    """Test event file scanning and sorting logic through EventLog."""
    with tempfile.TemporaryDirectory() as temp_dir:
        file_store = LocalFileStore(temp_dir)
        llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"))
        agent = Agent(llm=llm, tools=[])

        # Create event files with valid format (new pattern)
        events_dir = Path(temp_dir, "events")
        events_dir.mkdir()

        # Create files with different indices using valid event format
        event1 = SystemPromptEvent(
            id="abcdef01",
            source="agent",
            system_prompt=TextContent(text="system1"),
            tools=[],
        )
        (events_dir / "event-00000-abcdef01.json").write_text(
            event1.model_dump_json(exclude_none=True)
        )

        event2 = SystemPromptEvent(
            id="abcdef02",
            source="agent",
            system_prompt=TextContent(text="system2"),
            tools=[],
        )
        (events_dir / "event-00001-abcdef02.json").write_text(
            event2.model_dump_json(exclude_none=True)
        )

        # Invalid file should be ignored
        (events_dir / "invalid-file.json").write_text('{"type": "test"}')

        # Load state - EventLog should handle scanning
        conversation = Conversation(agent=agent, persist_filestore=file_store)

        # Should load valid events in order
        assert (
            len(conversation._state.events) == 2
        )  # May have additional events from Agent.init_state

        # Find our test events
        our_events = [
            e
            for e in conversation._state.events
            if isinstance(e, SystemPromptEvent) and e.id in ["abcdef01", "abcdef02"]
        ]
        assert len(our_events) == 2


def test_conversation_state_corrupted_event_handling():
    """Test handling of corrupted event files during replay."""
    with tempfile.TemporaryDirectory() as temp_dir:
        file_store = LocalFileStore(temp_dir)
        llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"))
        agent = Agent(llm=llm, tools=[])

        # Create event files with some corrupted
        events_dir = Path(temp_dir, "events")
        events_dir.mkdir()

        # Valid event with proper format
        valid_event = SystemPromptEvent(
            id="abcdef01",
            source="agent",
            system_prompt=TextContent(text="system"),
            tools=[],
        )
        (events_dir / "event-00000-abcdef01.json").write_text(
            valid_event.model_dump_json(exclude_none=True)
        )

        # Corrupted JSON - will be ignored by EventLog
        (events_dir / "event-00001-abcdef02.json").write_text('{"invalid": json}')

        # Empty file - will be ignored by EventLog
        (events_dir / "event-00002-abcdef03.json").write_text("")

        # Valid event with proper format
        valid_event2 = MessageEvent(
            id="abcdef04",
            source="user",
            llm_message=Message(role="user", content=[TextContent(text="hello")]),
        )
        (events_dir / "event-00003-abcdef04.json").write_text(
            valid_event2.model_dump_json(exclude_none=True)
        )

        # Load conversation - EventLog will fail on corrupted files
        with pytest.raises(json.JSONDecodeError):
            Conversation(agent=agent, persist_filestore=file_store)


def test_conversation_state_empty_filestore():
    """Test ConversationState behavior with empty filestore."""
    with tempfile.TemporaryDirectory() as temp_dir:
        file_store = LocalFileStore(temp_dir)
        llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"))
        agent = Agent(llm=llm, tools=[])

        # Create conversation with empty filestore
        conversation = Conversation(
            agent=agent, persist_filestore=file_store, visualize=False
        )

        # Should create new state
        assert conversation._state.id is not None
        assert len(conversation._state.events) == 1  # System prompt event
        assert isinstance(conversation._state.events[0], SystemPromptEvent)


def test_conversation_state_missing_base_state():
    """Test error handling when base_state.json is missing but events exist."""
    with tempfile.TemporaryDirectory() as temp_dir:
        file_store = LocalFileStore(temp_dir)
        llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"))
        agent = Agent(llm=llm, tools=[])

        # Create events directory with files but no base_state.json
        events_dir = Path(temp_dir, "events")
        events_dir.mkdir()
        event = SystemPromptEvent(
            id="abcdef01",
            source="agent",
            system_prompt=TextContent(text="system"),
            tools=[],
        )
        (events_dir / "event-00000-abcdef01.json").write_text(
            event.model_dump_json(exclude_none=True)
        )

        # Current implementation creates new conversation and ignores orphaned event files  # noqa: E501
        conversation = Conversation(agent=agent, persist_filestore=file_store)

        # Should create new state, not load the orphaned event file
        assert conversation._state.id is not None
        assert (
            len(conversation._state.events) >= 1
        )  # At least system prompt from Agent.init_state


def test_conversation_state_exclude_from_base_state():
    """Test that events are excluded from base state serialization."""
    with tempfile.TemporaryDirectory() as temp_dir:
        file_store = LocalFileStore(temp_dir)
        llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"))
        agent = Agent(llm=llm, tools=[])
        state = ConversationState.create(
            agent=agent,
            id=uuid.UUID("12345678-1234-5678-9abc-123456789004"),
            file_store=file_store,
        )

        # Add events
        event = SystemPromptEvent(
            source="agent", system_prompt=TextContent(text="system"), tools=[]
        )
        state.events.append(event)

        # State auto-saves, read base state file directly
        base_state_content = file_store.read("base_state.json")
        base_state_data = json.loads(base_state_content)

        # Events should not be in base state
        assert "events" not in base_state_data
        assert "agent" in base_state_data
        assert "id" in base_state_data


def test_conversation_state_thread_safety():
    """Test ConversationState thread safety with lock/unlock."""
    llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"))
    agent = Agent(llm=llm, tools=[])
    state = ConversationState.create(
        agent=agent, id=uuid.UUID("12345678-1234-5678-9abc-123456789005")
    )

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

    llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"))
    original_agent = Agent(llm=llm, tools=[])
    different_agent = DifferentAgent()

    with pytest.raises(ValueError, match="Cannot resolve from deserialized"):
        original_agent.resolve_diff_from_deserialized(different_agent)


def test_conversation_state_flags_persistence():
    """Test that conversation state flags are properly persisted."""
    with tempfile.TemporaryDirectory() as temp_dir:
        file_store = LocalFileStore(temp_dir)
        llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"))
        agent = Agent(llm=llm, tools=[])
        state = ConversationState.create(
            agent=agent,
            id=uuid.UUID("12345678-1234-5678-9abc-123456789006"),
            file_store=file_store,
        )

        # Set various flags
        state.agent_status = AgentExecutionStatus.FINISHED
        state.confirmation_policy = AlwaysConfirm()
        state.activated_knowledge_microagents = ["agent1", "agent2"]

        # State auto-saves, load using Conversation
        conversation = Conversation(
            agent=agent,
            persist_filestore=file_store,
            conversation_id=uuid.UUID("12345678-1234-5678-9abc-123456789006"),
        )
        loaded_state = conversation._state

        # Verify flags are preserved
        assert loaded_state.agent_status == AgentExecutionStatus.FINISHED
        assert loaded_state.confirmation_policy == AlwaysConfirm()
        assert loaded_state.activated_knowledge_microagents == ["agent1", "agent2"]
        # Test model_dump equality
        assert loaded_state.model_dump(mode="json") == state.model_dump(mode="json")
        # Verify key fields are preserved
        assert loaded_state.id == state.id
        assert loaded_state.agent.llm.model == state.agent.llm.model


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

        # Store original state dump and ID before deleting
        original_state_dump = conversation._state.model_dump(
            mode="json", exclude={"agent"}
        )
        conversation_id = conversation._state.id

        del conversation

        # Try with different LLM config (different API key should be resolved)
        new_llm = LLM(model="gpt-4o-mini", api_key=SecretStr("new-key"))
        new_agent = Agent(llm=new_llm, tools=[])

        # This should succeed because API key differences are resolved
        new_conversation = Conversation(
            agent=new_agent,
            persist_filestore=file_store,
            conversation_id=conversation_id,  # Use same ID
            visualize=False,
        )

        assert new_conversation._state.agent.llm.api_key is not None
        assert new_conversation._state.agent.llm.api_key.get_secret_value() == "new-key"
        # Test that the core state structure is preserved (excluding agent differences)
        new_dump = new_conversation._state.model_dump(mode="json", exclude={"agent"})
        assert new_dump == original_state_dump
