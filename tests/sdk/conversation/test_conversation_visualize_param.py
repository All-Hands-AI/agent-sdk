"""Tests for the Conversation class visualize parameter."""

from unittest.mock import Mock, patch

import pytest

from openhands.sdk.agent import Agent
from openhands.sdk.conversation import Conversation
from openhands.sdk.conversation.visualizer import ConversationVisualizer


@pytest.fixture
def mock_agent():
    """Create a mock agent for testing."""
    agent = Mock(spec=Agent)
    return agent


def test_conversation_with_visualize_true(mock_agent):
    """Test Conversation with visualize=True (default)."""
    conversation = Conversation(agent=mock_agent, visualize=True)

    # Should have a visualizer
    assert conversation._visualizer is not None
    assert isinstance(conversation._visualizer, ConversationVisualizer)

    # Agent should be initialized with callbacks that include visualizer
    mock_agent.init_state.assert_called_once()
    args, kwargs = mock_agent.init_state.call_args
    assert "on_event" in kwargs

    # The on_event callback should be composed of multiple callbacks
    on_event = kwargs["on_event"]
    assert callable(on_event)


def test_conversation_with_visualize_false(mock_agent):
    """Test Conversation with visualize=False."""
    conversation = Conversation(agent=mock_agent, visualize=False)

    # Should not have a visualizer
    assert conversation._visualizer is None

    # Agent should still be initialized with callbacks (just not visualizer)
    mock_agent.init_state.assert_called_once()
    args, kwargs = mock_agent.init_state.call_args
    assert "on_event" in kwargs

    # The on_event callback should still exist (for state persistence)
    on_event = kwargs["on_event"]
    assert callable(on_event)


def test_conversation_default_visualize_is_true(mock_agent):
    """Test that visualize defaults to True."""
    conversation = Conversation(agent=mock_agent)

    # Should have a visualizer by default
    assert conversation._visualizer is not None
    assert isinstance(conversation._visualizer, ConversationVisualizer)


def test_conversation_with_custom_callbacks_and_visualize_true(mock_agent):
    """Test Conversation with custom callbacks and visualize=True."""
    custom_callback = Mock()
    callbacks = [custom_callback]

    conversation = Conversation(agent=mock_agent, callbacks=callbacks, visualize=True)

    # Should have a visualizer
    assert conversation._visualizer is not None

    # Test that callbacks are composed correctly by triggering an event
    mock_agent.init_state.assert_called_once()
    args, kwargs = mock_agent.init_state.call_args
    on_event = kwargs["on_event"]

    # Create a mock event with proper visualize property
    from rich.text import Text

    mock_event = Mock()
    mock_event.visualize = Text("Test event content")
    on_event(mock_event)

    # Custom callback should have been called
    custom_callback.assert_called_once_with(mock_event)

    # Event should be in conversation state
    assert mock_event in conversation.state.events


def test_conversation_with_custom_callbacks_and_visualize_false(mock_agent):
    """Test Conversation with custom callbacks and visualize=False."""
    custom_callback = Mock()
    callbacks = [custom_callback]

    conversation = Conversation(agent=mock_agent, callbacks=callbacks, visualize=False)

    # Should not have a visualizer
    assert conversation._visualizer is None

    # Test that callbacks are composed correctly
    mock_agent.init_state.assert_called_once()
    args, kwargs = mock_agent.init_state.call_args
    on_event = kwargs["on_event"]

    # Create a mock event and trigger it
    mock_event = Mock()
    on_event(mock_event)

    # Custom callback should have been called
    custom_callback.assert_called_once_with(mock_event)

    # Event should be in conversation state
    assert mock_event in conversation.state.events


def test_conversation_callback_order(mock_agent):
    """Test that callbacks are executed in the correct order."""
    call_order = []

    def callback1(event):
        call_order.append("callback1")

    def callback2(event):
        call_order.append("callback2")

    # Mock the visualizer to track when it's called
    with patch(
        "openhands.sdk.conversation.conversation.create_default_visualizer"
    ) as mock_create_viz:
        mock_visualizer = Mock()
        mock_visualizer.on_event = Mock(
            side_effect=lambda e: call_order.append("visualizer")
        )
        mock_create_viz.return_value = mock_visualizer

        conversation = Conversation(
            agent=mock_agent, callbacks=[callback1, callback2], visualize=True
        )

        # Get the composed callback
        mock_agent.init_state.assert_called_once()
        args, kwargs = mock_agent.init_state.call_args
        on_event = kwargs["on_event"]

        # Trigger an event
        mock_event = Mock()
        on_event(mock_event)

        # Check order: visualizer, callback1, callback2, then state persistence
        assert call_order == ["visualizer", "callback1", "callback2"]

        # Event should be in state (state persistence happens last)
        assert mock_event in conversation.state.events


def test_conversation_no_callbacks_with_visualize_true(mock_agent):
    """Test Conversation with no custom callbacks but visualize=True."""
    conversation = Conversation(agent=mock_agent, callbacks=None, visualize=True)

    # Should have a visualizer
    assert conversation._visualizer is not None

    # Should still work with just visualizer and state persistence
    mock_agent.init_state.assert_called_once()
    args, kwargs = mock_agent.init_state.call_args
    on_event = kwargs["on_event"]

    # Should be able to handle events
    from rich.text import Text

    mock_event = Mock()
    mock_event.visualize = Text("Test event content")
    on_event(mock_event)

    # Event should be in state
    assert mock_event in conversation.state.events


def test_conversation_no_callbacks_with_visualize_false(mock_agent):
    """Test Conversation with no custom callbacks and visualize=False."""
    conversation = Conversation(agent=mock_agent, callbacks=None, visualize=False)

    # Should not have a visualizer
    assert conversation._visualizer is None

    # Should still work with just state persistence
    mock_agent.init_state.assert_called_once()
    args, kwargs = mock_agent.init_state.call_args
    on_event = kwargs["on_event"]

    # Should be able to handle events
    mock_event = Mock()
    on_event(mock_event)

    # Event should be in state
    assert mock_event in conversation.state.events
