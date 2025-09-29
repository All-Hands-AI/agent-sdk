"""Tests for ConversationState callback functionality."""

import uuid
from unittest.mock import Mock

from pydantic import SecretStr

from openhands.sdk import LLM, Agent
from openhands.sdk.conversation.state import AgentExecutionStatus, ConversationState
from openhands.sdk.io import InMemoryFileStore
from openhands.sdk.security.confirmation_policy import AlwaysConfirm


def _create_test_state():
    """Helper to create a test ConversationState."""
    llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="test-llm")
    agent = Agent(llm=llm, tools=[])
    return ConversationState.create(
        agent=agent,
        id=uuid.UUID("12345678-1234-5678-9abc-123456789001"),
        file_store=InMemoryFileStore(),
    )


def test_state_change_callback_registration():
    """Test that callbacks can be registered and removed."""
    state = _create_test_state()

    callback = Mock()

    # Test adding callback
    state.add_state_change_callback(callback)
    assert callback in state._state_change_callbacks

    # Test removing callback
    state.remove_state_change_callback(callback)
    assert callback not in state._state_change_callbacks


def test_state_change_callback_called():
    """Test that callbacks are called when state changes."""
    state = _create_test_state()

    callback = Mock()
    state.add_state_change_callback(callback)

    # Change a state field
    old_status = state.agent_status
    new_status = AgentExecutionStatus.RUNNING
    state.agent_status = new_status

    # Verify callback was called
    callback.assert_called_once_with("agent_status", old_status, new_status)


def test_state_change_callback_not_called_for_same_value():
    """Test that callbacks are not called when setting the same value."""
    state = _create_test_state()

    callback = Mock()
    state.add_state_change_callback(callback)

    # Set the same value
    current_status = state.agent_status
    state.agent_status = current_status

    # Verify callback was not called
    callback.assert_not_called()


def test_state_change_callback_not_called_for_private_attrs():
    """Test that callbacks are not called for private attributes."""
    state = _create_test_state()

    callback = Mock()
    state.add_state_change_callback(callback)

    # Change a private attribute
    state._autosave_enabled = False

    # Verify callback was not called
    callback.assert_not_called()


def test_state_change_callback_exception_handling():
    """Test that callback exceptions are handled gracefully."""
    state = _create_test_state()

    # Add a callback that raises an exception
    failing_callback = Mock(side_effect=Exception("Test exception"))
    working_callback = Mock()

    state.add_state_change_callback(failing_callback)
    state.add_state_change_callback(working_callback)

    # Change a state field - should not raise exception
    state.agent_status = AgentExecutionStatus.RUNNING

    # Both callbacks should have been called
    assert failing_callback.called
    assert working_callback.called


def test_multiple_callbacks():
    """Test that multiple callbacks are all called."""
    state = _create_test_state()

    callback1 = Mock()
    callback2 = Mock()
    callback3 = Mock()

    state.add_state_change_callback(callback1)
    state.add_state_change_callback(callback2)
    state.add_state_change_callback(callback3)

    # Change a state field
    old_status = state.agent_status
    new_status = AgentExecutionStatus.PAUSED
    state.agent_status = new_status

    # All callbacks should be called
    for callback in [callback1, callback2, callback3]:
        callback.assert_called_once_with("agent_status", old_status, new_status)


def test_callback_with_confirmation_policy_change():
    """Test callback is called when confirmation policy changes."""
    state = _create_test_state()

    callback = Mock()
    state.add_state_change_callback(callback)

    # Change confirmation policy
    old_policy = state.confirmation_policy
    new_policy = AlwaysConfirm()
    state.confirmation_policy = new_policy

    # Verify callback was called
    callback.assert_called_once_with("confirmation_policy", old_policy, new_policy)
