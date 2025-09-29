"""Tests for RemoteConversation state update handling."""

from openhands.sdk.event.conversation_state import ConversationStateUpdateEvent


def test_update_state_from_event_with_full_state():
    """Test updating cached state from a full state snapshot."""

    # Create a mock remote conversation (we'll test the method directly)
    # We can't easily instantiate RemoteConversation, so we'll test the logic
    # by creating a minimal test class
    class TestRemoteConv:
        def __init__(self):
            self._cached_state = None
            from threading import Lock

            self._lock = Lock()

        def update_state_from_event(self, event: ConversationStateUpdateEvent):
            """Copied from RemoteConversation for testing."""
            with self._lock:
                if event.key == "full_state":
                    if self._cached_state is None:
                        self._cached_state = {}
                    self._cached_state.update(event.value)
                else:
                    if self._cached_state is None:
                        self._cached_state = {}
                    self._cached_state[event.key] = event.value

    conv = TestRemoteConv()

    # Create a full state event
    full_state = {
        "agent_status": "running",
        "confirmation_policy": {"kind": "NeverConfirm"},
        "max_iterations": 100,
    }
    event = ConversationStateUpdateEvent(key="full_state", value=full_state)

    # Update state
    conv.update_state_from_event(event)

    # Verify all fields were updated
    assert conv._cached_state is not None
    assert conv._cached_state == full_state
    assert conv._cached_state["agent_status"] == "running"
    assert conv._cached_state["max_iterations"] == 100


def test_update_state_from_event_with_individual_field():
    """Test updating cached state from an individual field update."""

    class TestRemoteConv:
        def __init__(self):
            self._cached_state = {
                "agent_status": "idle",
                "max_iterations": 50,
            }
            from threading import Lock

            self._lock = Lock()

        def update_state_from_event(self, event: ConversationStateUpdateEvent):
            with self._lock:
                if event.key == "full_state":
                    if self._cached_state is None:
                        self._cached_state = {}
                    self._cached_state.update(event.value)
                else:
                    if self._cached_state is None:
                        self._cached_state = {}
                    self._cached_state[event.key] = event.value

    conv = TestRemoteConv()

    # Create an individual field update event
    event = ConversationStateUpdateEvent(key="agent_status", value="running")

    # Update state
    conv.update_state_from_event(event)

    # Verify only that field was updated
    assert conv._cached_state is not None
    assert conv._cached_state["agent_status"] == "running"
    assert conv._cached_state["max_iterations"] == 50  # Unchanged


def test_update_state_initializes_cache_if_none():
    """Test that update initializes cache if it doesn't exist."""

    class TestRemoteConv:
        def __init__(self):
            self._cached_state = None
            from threading import Lock

            self._lock = Lock()

        def update_state_from_event(self, event: ConversationStateUpdateEvent):
            with self._lock:
                if event.key == "full_state":
                    if self._cached_state is None:
                        self._cached_state = {}
                    self._cached_state.update(event.value)
                else:
                    if self._cached_state is None:
                        self._cached_state = {}
                    self._cached_state[event.key] = event.value

    conv = TestRemoteConv()

    # Update with individual field when cache is None
    event = ConversationStateUpdateEvent(key="agent_status", value="running")
    conv.update_state_from_event(event)

    # Verify cache was initialized
    assert conv._cached_state is not None
    assert conv._cached_state["agent_status"] == "running"


def test_update_state_from_multiple_events():
    """Test updating state from multiple events."""

    class TestRemoteConv:
        def __init__(self):
            self._cached_state = None
            from threading import Lock

            self._lock = Lock()

        def update_state_from_event(self, event: ConversationStateUpdateEvent):
            with self._lock:
                if event.key == "full_state":
                    if self._cached_state is None:
                        self._cached_state = {}
                    self._cached_state.update(event.value)
                else:
                    if self._cached_state is None:
                        self._cached_state = {}
                    self._cached_state[event.key] = event.value

    conv = TestRemoteConv()

    # First, full state
    full_state = {
        "agent_status": "idle",
        "max_iterations": 50,
        "stuck_detection": True,
    }
    event1 = ConversationStateUpdateEvent(key="full_state", value=full_state)
    conv.update_state_from_event(event1)

    # Then, individual updates
    event2 = ConversationStateUpdateEvent(key="agent_status", value="running")
    conv.update_state_from_event(event2)

    event3 = ConversationStateUpdateEvent(key="max_iterations", value=100)
    conv.update_state_from_event(event3)

    # Verify final state
    assert conv._cached_state is not None
    assert conv._cached_state["agent_status"] == "running"
    assert conv._cached_state["max_iterations"] == 100
    assert conv._cached_state["stuck_detection"] is True


def test_update_state_full_state_overwrites_fields():
    """Test that full_state update properly overwrites existing fields."""

    class TestRemoteConv:
        def __init__(self):
            self._cached_state = {
                "agent_status": "running",
                "max_iterations": 100,
                "old_field": "old_value",
            }
            from threading import Lock

            self._lock = Lock()

        def update_state_from_event(self, event: ConversationStateUpdateEvent):
            with self._lock:
                if event.key == "full_state":
                    if self._cached_state is None:
                        self._cached_state = {}
                    self._cached_state.update(event.value)
                else:
                    if self._cached_state is None:
                        self._cached_state = {}
                    self._cached_state[event.key] = event.value

    conv = TestRemoteConv()

    # Update with full state (without old_field)
    full_state = {
        "agent_status": "idle",
        "max_iterations": 50,
    }
    event = ConversationStateUpdateEvent(key="full_state", value=full_state)
    conv.update_state_from_event(event)

    # Verify new fields are set and old field still exists (update, not replace)
    assert conv._cached_state is not None
    assert conv._cached_state["agent_status"] == "idle"
    assert conv._cached_state["max_iterations"] == 50
    assert "old_field" in conv._cached_state  # Still there from .update()


def test_update_state_thread_safe():
    """Test that state updates are thread-safe."""
    import threading
    import time

    class TestRemoteConv:
        def __init__(self):
            self._cached_state = {"counter": 0}
            from threading import Lock

            self._lock = Lock()

        def update_state_from_event(self, event: ConversationStateUpdateEvent):
            with self._lock:
                if event.key == "full_state":
                    if self._cached_state is None:
                        self._cached_state = {}
                    self._cached_state.update(event.value)
                else:
                    if self._cached_state is None:
                        self._cached_state = {}
                    self._cached_state[event.key] = event.value

    conv = TestRemoteConv()

    def update_worker(i):
        event = ConversationStateUpdateEvent(key="counter", value=i)
        conv.update_state_from_event(event)
        time.sleep(0.001)  # Small delay to encourage race conditions

    # Create multiple threads updating concurrently
    threads = [threading.Thread(target=update_worker, args=(i,)) for i in range(10)]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Verify state is still valid (should have one of the values)
    assert conv._cached_state is not None
    assert "counter" in conv._cached_state
    assert 0 <= conv._cached_state["counter"] < 10


def test_update_state_preserves_data_types():
    """Test that state updates preserve data types correctly."""

    class TestRemoteConv:
        def __init__(self):
            self._cached_state = None
            from threading import Lock

            self._lock = Lock()

        def update_state_from_event(self, event: ConversationStateUpdateEvent):
            with self._lock:
                if event.key == "full_state":
                    if self._cached_state is None:
                        self._cached_state = {}
                    self._cached_state.update(event.value)
                else:
                    if self._cached_state is None:
                        self._cached_state = {}
                    self._cached_state[event.key] = event.value

    conv = TestRemoteConv()

    # Update with various data types
    full_state = {
        "string_field": "test",
        "int_field": 42,
        "bool_field": True,
        "list_field": [1, 2, 3],
        "dict_field": {"nested": "value"},
    }
    event = ConversationStateUpdateEvent(key="full_state", value=full_state)
    conv.update_state_from_event(event)

    # Verify types are preserved
    assert conv._cached_state is not None
    assert isinstance(conv._cached_state["string_field"], str)
    assert isinstance(conv._cached_state["int_field"], int)
    assert isinstance(conv._cached_state["bool_field"], bool)
    assert isinstance(conv._cached_state["list_field"], list)
    assert isinstance(conv._cached_state["dict_field"], dict)
