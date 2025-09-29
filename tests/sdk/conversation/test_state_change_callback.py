"""Tests for ConversationState callback mechanism."""

import uuid

import pytest
from pydantic import SecretStr

from openhands.sdk import LLM, Agent
from openhands.sdk.conversation.state import AgentExecutionStatus, ConversationState
from openhands.sdk.io import InMemoryFileStore


@pytest.fixture
def state():
    """Create a ConversationState for testing."""
    llm = LLM(model="gpt-4", api_key=SecretStr("test-key"), service_id="test-llm")
    agent = Agent(llm=llm)

    state = ConversationState(
        id=uuid.uuid4(),
        working_dir="/tmp/test",
        persistence_dir="/tmp/test/.state",
        agent=agent,
    )

    # Set up filestore and enable autosave so callbacks are triggered
    state._fs = InMemoryFileStore()
    state._autosave_enabled = True

    return state


def test_set_on_state_change_callback(state):
    """Test that callback can be set and is called when state changes."""
    callback_calls = []

    def callback(field_name: str, old_value, new_value):
        callback_calls.append((field_name, old_value, new_value))

    # Set the callback
    state.set_on_state_change(callback)

    # Change state - should trigger callback
    with state:
        state.agent_status = AgentExecutionStatus.RUNNING

    # Verify callback was called
    assert len(callback_calls) == 1
    assert callback_calls[0][0] == "agent_status"
    assert callback_calls[0][1] == AgentExecutionStatus.IDLE
    assert callback_calls[0][2] == AgentExecutionStatus.RUNNING


def test_callback_called_multiple_times(state):
    """Test that callback is called for multiple state changes."""
    callback_calls = []

    def callback(field_name: str, old_value, new_value):
        callback_calls.append((field_name, old_value, new_value))

    state.set_on_state_change(callback)

    # Make multiple state changes
    with state:
        state.agent_status = AgentExecutionStatus.RUNNING
        state.agent_status = AgentExecutionStatus.PAUSED
        state.agent_status = AgentExecutionStatus.FINISHED

    # Verify callback was called for each change
    assert len(callback_calls) == 3
    assert callback_calls[0][2] == AgentExecutionStatus.RUNNING
    assert callback_calls[1][2] == AgentExecutionStatus.PAUSED
    assert callback_calls[2][2] == AgentExecutionStatus.FINISHED


def test_callback_can_be_cleared(state):
    """Test that callback can be cleared by setting to None."""
    callback_calls = []

    def callback(field_name: str, old_value, new_value):
        callback_calls.append((field_name, old_value, new_value))

    # Set and then clear the callback
    state.set_on_state_change(callback)
    state.set_on_state_change(None)

    # Change state - callback should not be called
    with state:
        state.agent_status = AgentExecutionStatus.RUNNING

    # Verify callback was not called
    assert len(callback_calls) == 0


def test_callback_exception_does_not_break_state_change(state):
    """Test that exceptions in callback don't prevent state changes."""

    def bad_callback(field_name: str, old_value, new_value):
        raise ValueError("Callback error")

    state.set_on_state_change(bad_callback)

    # Change state - should not raise despite callback error
    with state:
        state.agent_status = AgentExecutionStatus.RUNNING

    # Verify state was still changed
    assert state.agent_status == AgentExecutionStatus.RUNNING


def test_callback_not_called_without_lock(state):
    """Test that callback is only called when state is modified within lock."""
    callback_calls = []

    def callback(field_name: str, old_value, new_value):
        callback_calls.append((field_name, old_value, new_value))

    state.set_on_state_change(callback)

    # This should still trigger callback since __setattr__ is called
    with state:
        state.agent_status = AgentExecutionStatus.RUNNING

    # Verify callback was called
    assert len(callback_calls) == 1


def test_callback_with_different_field_types(state):
    """Test callback works with different types of fields."""
    callback_calls = []

    def callback(field_name: str, old_value, new_value):
        callback_calls.append((field_name, old_value, new_value))

    state.set_on_state_change(callback)

    # Change different types of fields
    with state:
        state.agent_status = AgentExecutionStatus.RUNNING
        state.max_iterations = 100
        state.stuck_detection = False

    # Verify callback was called for each change
    assert len(callback_calls) == 3
    assert callback_calls[0][0] == "agent_status"
    assert callback_calls[1][0] == "max_iterations"
    assert callback_calls[2][0] == "stuck_detection"


def test_callback_receives_correct_old_value(state):
    """Test that callback receives the correct old value."""
    callback_calls = []

    def callback(field_name: str, old_value, new_value):
        callback_calls.append((field_name, old_value, new_value))

    # Set initial value
    with state:
        state.max_iterations = 50

    # Now set callback and change value again
    state.set_on_state_change(callback)

    with state:
        state.max_iterations = 100

    # Verify old value is correct
    assert len(callback_calls) == 1
    assert callback_calls[0][1] == 50
    assert callback_calls[0][2] == 100
