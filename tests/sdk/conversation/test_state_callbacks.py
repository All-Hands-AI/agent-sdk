"""Tests for ConversationState callback functionality."""

import uuid
from unittest.mock import Mock

from pydantic import SecretStr

from openhands.sdk import LLM, Agent
from openhands.sdk.conversation.base_state import AgentExecutionStatus
from openhands.sdk.conversation.state import ConversationState
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
    """Test that callback can be set and removed."""
    state = _create_test_state()

    callback = Mock()

    # Initially no callback
    assert state._on_state_change is None

    # Set callback
    state.set_on_state_change(callback)
    assert state._on_state_change is callback

    # Remove callback
    state.set_on_state_change(None)
    assert state._on_state_change is None


def test_state_change_callback_called():
    """Test that callback is called when state changes."""
    state = _create_test_state()

    callback = Mock()
    state.set_on_state_change(callback)

    # Change a state field
    old_status = state.agent_status
    new_status = AgentExecutionStatus.RUNNING
    state.agent_status = new_status

    # Verify callback was called
    callback.assert_called_once_with("agent_status", old_status, new_status)


def test_state_change_callback_not_called_for_same_value():
    """Test that callback is not called when setting the same value."""
    state = _create_test_state()

    callback = Mock()
    state.set_on_state_change(callback)

    # Set the same value
    current_status = state.agent_status
    state.agent_status = current_status

    # Verify callback was not called
    callback.assert_not_called()


def test_state_change_callback_not_called_for_private_attrs():
    """Test that callback is not called for private attributes."""
    state = _create_test_state()

    callback = Mock()
    state.set_on_state_change(callback)

    # Change a private attribute
    state._autosave_enabled = False

    # Verify callback was not called
    callback.assert_not_called()


def test_state_change_callback_exception_handling():
    """Test that callback exceptions are handled gracefully."""
    state = _create_test_state()

    # Set a callback that raises an exception
    failing_callback = Mock(side_effect=Exception("Test exception"))
    state.set_on_state_change(failing_callback)

    # Change a state field - should not raise exception
    state.agent_status = AgentExecutionStatus.RUNNING

    # Callback should have been called
    assert failing_callback.called


def test_callback_with_confirmation_policy_change():
    """Test callback is called when confirmation policy changes."""
    state = _create_test_state()

    callback = Mock()
    state.set_on_state_change(callback)

    # Change confirmation policy
    old_policy = state.confirmation_policy
    new_policy = AlwaysConfirm()
    state.confirmation_policy = new_policy

    # Verify callback was called
    callback.assert_called_once_with("confirmation_policy", old_policy, new_policy)
