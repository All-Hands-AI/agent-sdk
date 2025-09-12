"""Tests for the Subscription class."""

from unittest.mock import Mock

from openhands.sdk.conversation.subscription import Subscription
from openhands.sdk.event.llm_convertible import MessageEvent
from openhands.sdk.llm import Message, TextContent


def test_subscription_initialization():
    """Test that Subscription initializes with empty callback registry."""
    subscription = Subscription()
    assert subscription.callback_count == 0


def test_subscribe_returns_uuid():
    """Test that subscribe returns a UUID string."""
    subscription = Subscription()
    callback = Mock()

    callback_id = subscription.subscribe(callback)

    assert isinstance(callback_id, str)
    assert len(callback_id) == 36  # UUID4 string length
    assert subscription.callback_count == 1


def test_subscribe_multiple_callbacks():
    """Test subscribing multiple callbacks."""
    subscription = Subscription()
    callback1 = Mock()
    callback2 = Mock()

    id1 = subscription.subscribe(callback1)
    id2 = subscription.subscribe(callback2)

    assert id1 != id2
    assert subscription.callback_count == 2


def test_unsubscribe_existing_callback():
    """Test unsubscribing an existing callback."""
    subscription = Subscription()
    callback = Mock()

    callback_id = subscription.subscribe(callback)
    assert subscription.callback_count == 1

    result = subscription.unsubscribe(callback_id)

    assert result is True
    assert subscription.callback_count == 0


def test_unsubscribe_nonexistent_callback():
    """Test unsubscribing a non-existent callback."""
    subscription = Subscription()

    result = subscription.unsubscribe("non-existent-id")

    assert result is False
    assert subscription.callback_count == 0


def test_call_invokes_all_callbacks():
    """Test that __call__ invokes all registered callbacks."""
    subscription = Subscription()
    callback1 = Mock()
    callback2 = Mock()

    subscription.subscribe(callback1)
    subscription.subscribe(callback2)

    event = MessageEvent(
        source="user",
        llm_message=Message(role="user", content=[TextContent(text="test message")]),
    )

    subscription(event)

    callback1.assert_called_once_with(event)
    callback2.assert_called_once_with(event)


def test_on_event_alias():
    """Test that on_event is an alias for __call__."""
    subscription = Subscription()
    callback = Mock()

    subscription.subscribe(callback)

    event = MessageEvent(
        source="user",
        llm_message=Message(role="user", content=[TextContent(text="test message")]),
    )

    subscription.on_event(event)

    callback.assert_called_once_with(event)


def test_error_handling_in_callbacks():
    """Test that errors in one callback don't affect others."""
    subscription = Subscription()

    # Create callbacks where one raises an exception
    callback1 = Mock()
    callback2 = Mock(side_effect=Exception("Test error"))
    callback3 = Mock()

    subscription.subscribe(callback1)
    subscription.subscribe(callback2)
    subscription.subscribe(callback3)

    event = MessageEvent(
        source="user",
        llm_message=Message(role="user", content=[TextContent(text="test message")]),
    )

    # This should not raise an exception
    subscription(event)

    # All callbacks should have been called despite the error in callback2
    callback1.assert_called_once_with(event)
    callback2.assert_called_once_with(event)
    callback3.assert_called_once_with(event)


def test_clear_removes_all_callbacks():
    """Test that clear removes all registered callbacks."""
    subscription = Subscription()
    callback1 = Mock()
    callback2 = Mock()

    subscription.subscribe(callback1)
    subscription.subscribe(callback2)
    assert subscription.callback_count == 2

    subscription.clear()

    assert subscription.callback_count == 0


def test_clear_empty_subscription():
    """Test that clear works on empty subscription."""
    subscription = Subscription()
    assert subscription.callback_count == 0

    subscription.clear()

    assert subscription.callback_count == 0


def test_callback_count_property():
    """Test the callback_count property."""
    subscription = Subscription()
    assert subscription.callback_count == 0

    id1 = subscription.subscribe(Mock())
    assert subscription.callback_count == 1

    id2 = subscription.subscribe(Mock())
    assert subscription.callback_count == 2

    subscription.unsubscribe(id1)
    assert subscription.callback_count == 1

    subscription.unsubscribe(id2)
    assert subscription.callback_count == 0


def test_subscription_with_real_callback_function():
    """Test subscription with a real callback function."""
    subscription = Subscription()
    events_received = []

    def callback(event):
        events_received.append(event.id)

    subscription.subscribe(callback)

    event = MessageEvent(
        source="user",
        llm_message=Message(role="user", content=[TextContent(text="test message")]),
    )

    subscription(event)

    assert len(events_received) == 1
    assert events_received[0] == event.id


def test_multiple_events_to_same_callbacks():
    """Test sending multiple events to the same set of callbacks."""
    subscription = Subscription()
    callback1_events = []
    callback2_events = []

    def callback1(event):
        callback1_events.append(event.id)

    def callback2(event):
        callback2_events.append(event.id)

    subscription.subscribe(callback1)
    subscription.subscribe(callback2)

    event1 = MessageEvent(
        source="user",
        llm_message=Message(role="user", content=[TextContent(text="message 1")]),
    )
    event2 = MessageEvent(
        source="user",
        llm_message=Message(role="user", content=[TextContent(text="message 2")]),
    )

    subscription(event1)
    subscription(event2)

    assert len(callback1_events) == 2
    assert len(callback2_events) == 2
    assert callback1_events == [event1.id, event2.id]
    assert callback2_events == [event1.id, event2.id]
