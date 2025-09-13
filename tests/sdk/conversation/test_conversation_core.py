"""Core high-quality tests for Conversation class focusing on essential
functionality."""

import tempfile
from unittest.mock import Mock

import pytest
from pydantic import SecretStr

from openhands.sdk.agent import Agent
from openhands.sdk.conversation import Conversation
from openhands.sdk.event.llm_convertible import MessageEvent
from openhands.sdk.io.local import LocalFileStore
from openhands.sdk.io.memory import InMemoryFileStore
from openhands.sdk.llm import LLM, Message, TextContent


def create_test_agent() -> Agent:
    """Create a test agent."""
    llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"))
    return Agent(llm=llm, tools=[])


def create_test_event(event_id: str, content: str = "Test content") -> MessageEvent:
    """Create a test MessageEvent with specific ID."""
    event = MessageEvent(
        llm_message=Message(role="user", content=[TextContent(text=content)]),
        source="user",
    )
    event.id = event_id
    return event


def test_conversation_basic_creation():
    """Test basic conversation creation and properties."""
    fs = InMemoryFileStore()
    agent = create_test_agent()

    conv = Conversation(agent=agent, persist_filestore=fs)

    # Basic properties should be set
    assert conv.id is not None
    assert len(conv.id) > 10  # UUID format
    assert conv.state is not None
    assert conv.state.agent == agent


def test_conversation_event_log_functionality():
    """Test EventLog integration with Conversation."""
    fs = InMemoryFileStore()
    agent = create_test_agent()

    conv = Conversation(agent=agent, persist_filestore=fs)

    # Add events directly to test EventLog functionality
    events = [
        create_test_event("event-1", "First message"),
        create_test_event("event-2", "Second message"),
        create_test_event("event-3", "Third message"),
    ]

    for event in events:
        conv.state.events.append(event)

    # Test basic EventLog functionality
    total_events = len(conv.state.events)
    assert total_events >= 3  # May have additional events from Agent.init_state

    # Find our test events
    our_events = [e for e in conv.state.events if e.id.startswith("event-")]
    assert len(our_events) == 3
    assert our_events[0].id == "event-1"
    assert our_events[1].id == "event-2"
    assert our_events[2].id == "event-3"

    # Test iteration
    event_ids = [e.id for e in our_events]
    assert event_ids == ["event-1", "event-2", "event-3"]


def test_conversation_state_persistence():
    """Test conversation state persistence to file store."""
    fs = InMemoryFileStore()
    agent = create_test_agent()

    conv = Conversation(agent=agent, persist_filestore=fs)

    # Add an event
    event = create_test_event("persist-test", "Persistence test")
    conv.state.events.append(event)

    # State should auto-save when events are added
    # Check that files were created
    all_files = fs.list("")
    assert len(all_files) > 0

    # Should have base state file
    base_state_exists = any("base_state.json" in f for f in all_files)
    assert base_state_exists

    # Should have events directory
    events_files = fs.list("events")
    assert len(events_files) > 0


def test_conversation_with_custom_id():
    """Test conversation creation with custom ID."""
    fs = InMemoryFileStore()
    agent = create_test_agent()

    custom_id = "my-custom-conversation-id"
    conv = Conversation(agent=agent, persist_filestore=fs, conversation_id=custom_id)

    assert conv.id == custom_id
    assert conv.state.id == custom_id


def test_conversation_event_id_validation():
    """Test that EventLog prevents duplicate event IDs."""
    import pytest

    fs = InMemoryFileStore()
    agent = create_test_agent()

    conv = Conversation(agent=agent, persist_filestore=fs)

    # Add first event
    event1 = create_test_event("unique-id-1", "First event")
    conv.state.events.append(event1)

    # Add event with duplicate ID - should raise ValueError
    event2 = create_test_event("unique-id-1", "Second event")
    with pytest.raises(
        ValueError, match="Event with ID 'unique-id-1' already exists at index 1"
    ):
        conv.state.events.append(event2)

    # Only the first event should be in the log
    our_events = [e for e in conv.state.events if e.id == "unique-id-1"]
    assert len(our_events) == 1


@pytest.mark.forked  # Use pytest-forked to isolate memory-intensive test
def test_conversation_large_event_handling():
    """Test conversation handling of many events with memory usage monitoring."""
    import gc
    import os

    import psutil

    process = psutil.Process(os.getpid())
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB

    fs = InMemoryFileStore()
    agent = create_test_agent()

    conv = Conversation(agent=agent, persist_filestore=fs)

    # Add many events to test memory bounds
    num_events = 5000  # Large number to test memory usage
    for i in range(num_events):
        event = create_test_event(f"bulk-event-{i:04d}", f"Message {i}")
        conv.state.events.append(event)

        # Check memory usage periodically
        if i % 1000 == 0 and i > 0:
            gc.collect()  # Force garbage collection

            assert process is not None
            current_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_growth = current_memory - initial_memory
            # Memory should not grow excessively (allow reasonable growth)
            assert memory_growth < 500, (
                f"Memory usage grew too much: {memory_growth:.2f}MB after {i} events"
            )

    # Test that all events are accessible
    total_events = len(conv.state.events)
    assert total_events >= num_events

    # Find our test events
    our_events = [e for e in conv.state.events if e.id.startswith("bulk-event-")]
    assert len(our_events) == num_events

    # Test random access
    assert our_events[2500].id == "bulk-event-2500"
    assert our_events[4999].id == "bulk-event-4999"

    # Test iteration performance
    event_count = sum(1 for e in conv.state.events if e.id.startswith("bulk-event-"))
    assert event_count == num_events

    # Final memory check
    gc.collect()
    final_memory = process.memory_info().rss / 1024 / 1024  # MB
    total_memory_growth = final_memory - initial_memory

    # Ensure memory usage stays bounded (allow reasonable growth)
    assert total_memory_growth < 1000, (
        f"Total memory growth too high: {total_memory_growth:.2f}MB "
        f"for {num_events} events"
    )
    print(
        f"Memory usage: initial {initial_memory:.2f}MB, "
        f"final {final_memory:.2f}MB, "
        f"growth {total_memory_growth:.2f}MB"
    )


def test_conversation_error_handling():
    """Test conversation handles errors gracefully."""
    # Test with mock file store that has limited functionality
    mock_fs = Mock()
    mock_fs.exists.return_value = False
    mock_fs.list.return_value = []
    mock_fs.read.side_effect = FileNotFoundError("File not found")

    agent = create_test_agent()

    # Should create conversation despite file store limitations
    conv = Conversation(agent=agent, persist_filestore=mock_fs)

    # Should have basic properties
    assert conv.id is not None
    assert conv.state is not None


def test_conversation_memory_vs_local_filestore():
    """Test conversation works with both InMemoryFileStore and LocalFileStore."""
    agent = create_test_agent()

    # Test with InMemoryFileStore
    mem_fs = InMemoryFileStore()
    conv1 = Conversation(agent=agent, persist_filestore=mem_fs)

    event1 = create_test_event("memory-test", "Memory test")
    conv1.state.events.append(event1)
    # State auto-saves when events are added

    # Test with LocalFileStore
    with tempfile.TemporaryDirectory() as temp_dir:
        local_fs = LocalFileStore(temp_dir)
        conv2 = Conversation(agent=agent, persist_filestore=local_fs)

        event2 = create_test_event("local-test", "Local test")
        conv2.state.events.append(event2)
        # State auto-saves when events are added

        # Verify files were created
        files = local_fs.list("")
        assert len(files) > 0
