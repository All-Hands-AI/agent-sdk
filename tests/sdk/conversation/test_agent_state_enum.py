"""Test the new AgentExecutionState enum functionality."""

from pydantic import SecretStr

from openhands.sdk import Agent, Conversation
from openhands.sdk.conversation.state import AgentExecutionState
from openhands.sdk.llm import LLM


def test_agent_execution_state_enum_basic():
    """Test basic AgentExecutionState enum functionality."""
    llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"))
    agent = Agent(llm=llm, tools=[])
    conversation = Conversation(agent=agent)

    # Test initial state
    assert conversation.state.agent_state == AgentExecutionState.IDLE
    assert conversation.state.agent_finished is False
    assert conversation.state.agent_paused is False
    assert conversation.state.agent_waiting_for_confirmation is False

    # Test setting enum directly
    conversation.state.agent_state = AgentExecutionState.RUNNING
    assert conversation.state.agent_state == AgentExecutionState.RUNNING
    assert conversation.state.agent_finished is False
    assert conversation.state.agent_paused is False
    assert conversation.state.agent_waiting_for_confirmation is False

    # Test setting to FINISHED
    conversation.state.agent_state = AgentExecutionState.FINISHED
    assert conversation.state.agent_state == AgentExecutionState.FINISHED
    assert conversation.state.agent_finished is True
    assert conversation.state.agent_paused is False
    assert conversation.state.agent_waiting_for_confirmation is False

    # Test setting to PAUSED
    conversation.state.agent_state = AgentExecutionState.PAUSED
    assert conversation.state.agent_state == AgentExecutionState.PAUSED
    assert conversation.state.agent_finished is False
    assert conversation.state.agent_paused is True
    assert conversation.state.agent_waiting_for_confirmation is False

    # Test setting to WAITING_FOR_CONFIRMATION
    conversation.state.agent_state = AgentExecutionState.WAITING_FOR_CONFIRMATION
    assert (
        conversation.state.agent_state == AgentExecutionState.WAITING_FOR_CONFIRMATION
    )
    assert conversation.state.agent_finished is False
    assert conversation.state.agent_paused is False
    assert conversation.state.agent_waiting_for_confirmation is True


def test_backward_compatibility_boolean_to_enum():
    """Test that setting boolean fields updates the enum (backward compatibility)."""
    llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"))
    agent = Agent(llm=llm, tools=[])
    conversation = Conversation(agent=agent)

    # Test setting agent_finished
    conversation.state.agent_finished = True
    assert conversation.state.agent_state == AgentExecutionState.FINISHED
    assert conversation.state.agent_finished is True

    # Reset and test agent_paused
    conversation.state.agent_finished = False
    conversation.state.agent_paused = True
    assert conversation.state.agent_state == AgentExecutionState.PAUSED
    assert conversation.state.agent_paused is True

    # Reset and test agent_waiting_for_confirmation
    conversation.state.agent_paused = False
    conversation.state.agent_waiting_for_confirmation = True
    assert (
        conversation.state.agent_state == AgentExecutionState.WAITING_FOR_CONFIRMATION
    )
    assert conversation.state.agent_waiting_for_confirmation is True

    # Reset all to false should go to IDLE
    conversation.state.agent_waiting_for_confirmation = False
    assert conversation.state.agent_state == AgentExecutionState.IDLE


def test_enum_serialization():
    """Test that the enum serializes and deserializes correctly."""
    llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"))
    agent = Agent(llm=llm, tools=[])
    conversation = Conversation(agent=agent)

    # Set to different states and test serialization
    conversation.state.agent_state = AgentExecutionState.FINISHED
    serialized = conversation.state.model_dump_json()
    assert '"agent_state":"finished"' in serialized

    conversation.state.agent_state = AgentExecutionState.PAUSED
    serialized = conversation.state.model_dump_json()
    assert '"agent_state":"paused"' in serialized

    conversation.state.agent_state = AgentExecutionState.WAITING_FOR_CONFIRMATION
    serialized = conversation.state.model_dump_json()
    assert '"agent_state":"waiting_for_confirmation"' in serialized
