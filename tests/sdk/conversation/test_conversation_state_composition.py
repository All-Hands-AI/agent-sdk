"""Test ConversationState composition-based lock implementation."""

import threading
import time
import uuid
from collections import deque

from pydantic import SecretStr

from openhands.sdk.agent import Agent
from openhands.sdk.conversation.state import ConversationState
from openhands.sdk.llm import LLM
from openhands.sdk.workspace.local import LocalWorkspace


def test_conversation_state_lock_composition():
    """Test that ConversationState uses composition for lock functionality."""
    llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="test-llm")
    agent = Agent(llm=llm, tools=[])
    state = ConversationState.create(
        workspace=LocalWorkspace(working_dir="/tmp"),
        agent=agent,
        id=uuid.UUID("12345678-1234-5678-9abc-123456789006"),
    )

    # Verify that ConversationState has a _lock attribute (composition)
    assert hasattr(state, "_lock")
    assert state._lock is not None

    # Verify that ConversationState no longer inherits from FIFOLock
    from openhands.sdk.conversation.fifo_lock import FIFOLock

    assert not isinstance(state, FIFOLock)
    assert isinstance(state._lock, FIFOLock)

    # Test basic lock functionality through delegation
    assert not state.locked()
    assert not state.owned()

    # Test acquire/release
    state.acquire()
    assert state.locked()
    assert state.owned()

    state.release()
    assert not state.locked()
    assert not state.owned()


def test_conversation_state_context_manager():
    """Test ConversationState context manager functionality."""
    llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="test-llm")
    agent = Agent(llm=llm, tools=[])
    state = ConversationState.create(
        workspace=LocalWorkspace(working_dir="/tmp"),
        agent=agent,
        id=uuid.UUID("12345678-1234-5678-9abc-123456789007"),
    )

    # Test context manager
    with state:
        assert state.locked()
        assert state.owned()

    assert not state.locked()
    assert not state.owned()


def test_conversation_state_lock_fairness():
    """Test that ConversationState maintains FIFO lock fairness."""
    llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="test-llm")
    agent = Agent(llm=llm, tools=[])
    state = ConversationState.create(
        workspace=LocalWorkspace(working_dir="/tmp"),
        agent=agent,
        id=uuid.UUID("12345678-1234-5678-9abc-123456789008"),
    )

    acquisition_order = deque()
    threads = []
    thread_events = [threading.Event() for _ in range(5)]

    def worker(thread_id: int, my_event: threading.Event):
        my_event.wait()
        with state:
            acquisition_order.append(thread_id)
            time.sleep(0.001)

    # Create threads
    for i in range(5):
        thread = threading.Thread(target=worker, args=(i, thread_events[i]))
        threads.append(thread)

    # Start all threads
    for thread in threads:
        thread.start()

    # Signal threads in order
    for i in range(5):
        thread_events[i].set()
        time.sleep(0.002)

    # Wait for completion
    for thread in threads:
        thread.join()

    # Check FIFO order
    expected_order = list(range(5))
    actual_order = list(acquisition_order)
    assert actual_order == expected_order


def test_conversation_state_lock_reentrancy():
    """Test ConversationState lock reentrancy."""
    llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="test-llm")
    agent = Agent(llm=llm, tools=[])
    state = ConversationState.create(
        workspace=LocalWorkspace(working_dir="/tmp"),
        agent=agent,
        id=uuid.UUID("12345678-1234-5678-9abc-123456789009"),
    )

    # Test reentrancy
    state.acquire()
    assert state.locked()
    assert state.owned()

    state.acquire()  # Second acquire
    assert state.locked()
    assert state.owned()

    state.release()  # First release
    assert state.locked()  # Still locked
    assert state.owned()

    state.release()  # Second release
    assert not state.locked()
    assert not state.owned()
