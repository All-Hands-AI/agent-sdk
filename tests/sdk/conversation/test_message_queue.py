"""
Unit tests for message queueing functionality in Conversation class.

Tests the core behavior: queue messages when agent is busy and process sequentially.
Key requirements:
1. Original send_message() method behavior unchanged (returns None)
2. New send_message_with_queue_status() method provides queue status information
3. Messages queued when agent is running, processed immediately when idle
4. Queue processing is thread-safe and respects agent states
5. Integration with existing conversation features (callbacks, confirmation mode)
"""

import threading
import time
from unittest.mock import patch

import pytest
from pydantic import SecretStr

from openhands.sdk.agent import Agent
from openhands.sdk.conversation import Conversation
from openhands.sdk.conversation.state import AgentExecutionStatus
from openhands.sdk.io.memory import InMemoryFileStore
from openhands.sdk.llm import LLM, Message, TextContent


def create_test_agent() -> Agent:
    """Create a test agent for testing."""
    llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"))
    return Agent(llm=llm, tools=[])


def test_queue_initialization():
    """Test that message queue is properly initialized."""
    agent = create_test_agent()
    fs = InMemoryFileStore()
    conv = Conversation(agent=agent, persist_filestore=fs)

    # Queue should be empty initially
    assert len(conv._message_queue) == 0

    # Queue status should show empty queue
    status = conv.get_queue_status()
    assert status["queue_size"] == 0
    assert status["has_queued_messages"] is False
    assert status["agent_status"] == "idle"


def test_send_message_original_method_unchanged():
    """Test that original send_message method behavior is unchanged."""
    agent = create_test_agent()
    fs = InMemoryFileStore()
    conv = Conversation(agent=agent, persist_filestore=fs)

    message = Message(role="user", content=[TextContent(text="Test message")])

    # Original method should return None
    result = conv.send_message(message)
    assert result is None

    # Should add event to conversation state
    assert len(conv.state.events) > 0


def test_send_message_with_queue_status_immediate_processing():
    """Test new method when agent is idle (immediate processing)."""
    agent = create_test_agent()
    fs = InMemoryFileStore()
    conv = Conversation(agent=agent, persist_filestore=fs)

    message = Message(role="user", content=[TextContent(text="Test message")])

    # New method should return dict with status
    result = conv.send_message_with_queue_status(message)

    assert isinstance(result, dict)
    assert result["queued"] is False
    assert result["processed_immediately"] is True
    assert result["agent_status"] == "idle"
    assert "queue_position" not in result or result["queue_position"] is None

    # Should still add event to conversation state
    assert len(conv.state.events) > 0


def test_send_message_with_queue_status_when_busy():
    """Test new method when agent is busy (queueing)."""
    agent = create_test_agent()
    fs = InMemoryFileStore()
    conv = Conversation(agent=agent, persist_filestore=fs)

    # Manually set agent status to running
    with conv.state:
        conv.state.agent_status = AgentExecutionStatus.RUNNING

    message = Message(role="user", content=[TextContent(text="Test message")])
    result = conv.send_message_with_queue_status(message)

    assert isinstance(result, dict)
    assert result["queued"] is True
    assert result["queue_position"] == 1
    assert result["agent_status"] == "running"
    assert (
        "processed_immediately" not in result or result["processed_immediately"] is None
    )

    # Message should be in queue
    assert len(conv._message_queue) == 1
    assert conv._message_queue[0] == message

    # Queue status should reflect queued message
    status = conv.get_queue_status()
    assert status["queue_size"] == 1
    assert status["has_queued_messages"] is True


def test_multiple_messages_queuing():
    """Test queueing multiple messages when agent is busy."""
    agent = create_test_agent()
    fs = InMemoryFileStore()
    conv = Conversation(agent=agent, persist_filestore=fs)

    # Set agent to running
    with conv.state:
        conv.state.agent_status = AgentExecutionStatus.RUNNING

    messages = [
        Message(role="user", content=[TextContent(text=f"Message {i}")])
        for i in range(3)
    ]

    results = []
    for i, message in enumerate(messages):
        result = conv.send_message_with_queue_status(message)
        results.append(result)

        # Check queue position increases
        assert result["queued"] is True
        assert result["queue_position"] == i + 1

    # All messages should be in queue
    assert len(conv._message_queue) == 3
    for i, message in enumerate(messages):
        assert conv._message_queue[i] == message

    # Queue status should reflect all messages
    status = conv.get_queue_status()
    assert status["queue_size"] == 3
    assert status["has_queued_messages"] is True


def test_process_queued_messages_when_idle():
    """Test that queued messages are processed when agent becomes idle."""
    agent = create_test_agent()
    fs = InMemoryFileStore()
    conv = Conversation(agent=agent, persist_filestore=fs, visualize=False)

    # Add messages to queue manually
    messages = [
        Message(role="user", content=[TextContent(text=f"Message {i}")])
        for i in range(2)
    ]

    for message in messages:
        conv._message_queue.append(message)

    # Mock both send_message and run to avoid actual execution
    with patch.object(conv, "send_message") as mock_send_message:
        with patch.object(conv, "run"):
            # Make agent status indicate it should not run after processing
            with conv.state:
                conv.state.agent_status = AgentExecutionStatus.FINISHED

            # Process queued messages
            conv._process_queued_messages()

            # send_message should have been called for each message
            assert mock_send_message.call_count == 2
            # Queue should be empty
            assert len(conv._message_queue) == 0


def test_process_queued_messages_stops_when_agent_busy():
    """Test that queue processing stops if agent becomes busy again."""
    agent = create_test_agent()
    fs = InMemoryFileStore()
    conv = Conversation(agent=agent, persist_filestore=fs, visualize=False)

    # Add messages to queue
    messages = [
        Message(role="user", content=[TextContent(text=f"Message {i}")])
        for i in range(3)
    ]

    for message in messages:
        conv._message_queue.append(message)

    # Mock send_message to simulate agent becoming busy after first message
    original_send_message = conv.send_message
    call_count = 0

    def mock_send_message(message):
        nonlocal call_count
        call_count += 1
        if call_count == 2:  # After second message, make agent busy
            with conv.state:
                conv.state.agent_status = AgentExecutionStatus.RUNNING
        return original_send_message(message)

    with patch.object(conv, "send_message", side_effect=mock_send_message):
        with patch.object(conv, "run"):
            conv._process_queued_messages()

    # Should have processed one message and stopped
    assert len(conv._message_queue) == 2  # 2 messages remaining


def test_queue_processing_with_confirmation_mode():
    """Test queue processing respects confirmation mode."""
    agent = create_test_agent()
    fs = InMemoryFileStore()
    conv = Conversation(agent=agent, persist_filestore=fs, visualize=False)

    # Add message to queue
    message = Message(role="user", content=[TextContent(text="Test message")])
    conv._message_queue.append(message)

    # Mock send_message to set agent to waiting for confirmation
    def mock_send_message(msg):
        with conv.state:
            conv.state.agent_status = AgentExecutionStatus.WAITING_FOR_CONFIRMATION

    with patch.object(conv, "send_message", side_effect=mock_send_message):
        with patch.object(conv, "run") as mock_run:
            conv._process_queued_messages()

            # Run should not be called when waiting for confirmation
            mock_run.assert_not_called()


def test_concurrent_queue_operations():
    """Test that queue operations are thread-safe."""
    agent = create_test_agent()
    fs = InMemoryFileStore()
    conv = Conversation(agent=agent, persist_filestore=fs, visualize=False)

    # Set agent to running to force queueing
    with conv.state:
        conv.state.agent_status = AgentExecutionStatus.RUNNING

    results = []
    errors = []

    def send_message_thread(thread_id: int):
        try:
            message = Message(
                role="user",
                content=[TextContent(text=f"Message from thread {thread_id}")],
            )
            result = conv.send_message_with_queue_status(message)
            results.append((thread_id, result))
        except Exception as e:
            errors.append((thread_id, e))

    # Start multiple threads
    threads = []
    for i in range(5):
        thread = threading.Thread(target=send_message_thread, args=(i,))
        threads.append(thread)
        thread.start()

    # Wait for all threads
    for thread in threads:
        thread.join()

    # Check results
    assert len(errors) == 0, f"Errors occurred: {errors}"
    assert len(results) == 5

    # All messages should be queued
    for thread_id, result in results:
        assert result["queued"] is True
        assert isinstance(result["queue_position"], int)
        assert result["queue_position"] > 0

    # Queue should contain all messages
    assert len(conv._message_queue) == 5


def test_queue_status_thread_safety():
    """Test that get_queue_status is thread-safe."""
    agent = create_test_agent()
    fs = InMemoryFileStore()
    conv = Conversation(agent=agent, persist_filestore=fs, visualize=False)

    statuses = []
    errors = []

    def get_status_thread(thread_id: int):
        try:
            for _ in range(10):  # Multiple calls per thread
                status = conv.get_queue_status()
                statuses.append((thread_id, status))
                time.sleep(0.001)  # Small delay
        except Exception as e:
            errors.append((thread_id, e))

    # Start multiple threads
    threads = []
    for i in range(3):
        thread = threading.Thread(target=get_status_thread, args=(i,))
        threads.append(thread)
        thread.start()

    # Wait for all threads
    for thread in threads:
        thread.join()

    # Check results
    assert len(errors) == 0, f"Errors occurred: {errors}"
    assert len(statuses) == 30  # 3 threads * 10 calls each

    # All statuses should be valid
    for thread_id, status in statuses:
        assert isinstance(status, dict)
        assert "queue_size" in status
        assert "agent_status" in status
        assert "has_queued_messages" in status


def test_send_message_validation_both_methods():
    """Test that both methods validate message roles properly."""
    agent = create_test_agent()
    fs = InMemoryFileStore()
    conv = Conversation(agent=agent, persist_filestore=fs)

    # Test with invalid role
    invalid_message = Message(role="assistant", content=[TextContent(text="Test")])

    # Both methods should raise assertion error
    with pytest.raises(AssertionError):
        conv.send_message(invalid_message)

    with pytest.raises(AssertionError):
        conv.send_message_with_queue_status(invalid_message)


def test_queue_status_consistency():
    """Test that queue status remains consistent across operations."""
    agent = create_test_agent()
    fs = InMemoryFileStore()
    conv = Conversation(agent=agent, persist_filestore=fs)

    # Initial status
    status = conv.get_queue_status()
    assert status["queue_size"] == 0
    assert not status["has_queued_messages"]

    # Set agent to running and add messages
    with conv.state:
        conv.state.agent_status = AgentExecutionStatus.RUNNING

    messages = []
    for i in range(3):
        message = Message(role="user", content=[TextContent(text=f"Message {i}")])
        conv.send_message_with_queue_status(message)
        messages.append(message)

        # Status should be consistent with queue state
        status = conv.get_queue_status()
        assert status["queue_size"] == i + 1
        assert status["has_queued_messages"] is True
        assert status["agent_status"] == "running"


def test_queue_with_conversation_callbacks():
    """Test that queueing works properly with conversation callbacks."""
    agent = create_test_agent()
    fs = InMemoryFileStore()

    callback_events = []

    def test_callback(event):
        callback_events.append(event)

    conv = Conversation(
        agent=agent, persist_filestore=fs, callbacks=[test_callback], visualize=False
    )

    # Send message when idle (immediate processing)
    message = Message(role="user", content=[TextContent(text="Test message")])
    result = conv.send_message_with_queue_status(message)

    assert result["queued"] is False
    assert len(callback_events) > 0  # Callback should be triggered


def test_queue_preserves_message_content():
    """Test that queued messages preserve their content correctly."""
    agent = create_test_agent()
    fs = InMemoryFileStore()
    conv = Conversation(agent=agent, persist_filestore=fs, visualize=False)

    # Set agent to running
    with conv.state:
        conv.state.agent_status = AgentExecutionStatus.RUNNING

    # Send message with specific content
    original_text = "This is a test message with specific content"
    message = Message(role="user", content=[TextContent(text=original_text)])

    result = conv.send_message_with_queue_status(message)
    assert result["queued"] is True

    # Check queued message preserves content
    queued_message = conv._message_queue[0]
    assert queued_message.role == "user"
    assert len(queued_message.content) == 1
    assert isinstance(queued_message.content[0], TextContent)
    assert queued_message.content[0].text == original_text


def test_queue_run_integration():
    """Test that run() method properly processes queued messages."""
    agent = create_test_agent()
    fs = InMemoryFileStore()
    conv = Conversation(agent=agent, persist_filestore=fs, visualize=False)

    # Add messages to queue manually
    messages = [
        Message(role="user", content=[TextContent(text=f"Message {i}")])
        for i in range(2)
    ]

    for message in messages:
        conv._message_queue.append(message)

    # Mock the _process_queued_messages method to verify it's called
    # and avoid the complexity of mocking frozen Agent
    with patch.object(conv, "_process_queued_messages") as mock_process_queue:
        # Set agent status to finished to avoid infinite loop
        with conv.state:
            conv.state.agent_status = AgentExecutionStatus.FINISHED

        # Call run which should process queue at the end
        conv.run()

        # _process_queued_messages should have been called
        mock_process_queue.assert_called_once()
