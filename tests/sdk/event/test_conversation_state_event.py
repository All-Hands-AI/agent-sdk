"""Tests for ConversationStateUpdateEvent."""

import json
import uuid

import pytest
from pydantic import SecretStr

from openhands.sdk import LLM, Agent
from openhands.sdk.conversation.state import AgentExecutionStatus, ConversationState
from openhands.sdk.event.conversation_state import ConversationStateUpdateEvent
from openhands.sdk.io import InMemoryFileStore
from openhands.sdk.security.confirmation_policy import NeverConfirm


@pytest.fixture
def state():
    """Create a ConversationState for testing."""
    # Set an agent to test serialization
    llm = LLM(model="gpt-4", api_key=SecretStr("test-key"), service_id="test-llm")
    agent = Agent(llm=llm)

    state = ConversationState(
        id=uuid.uuid4(),
        working_dir="/tmp/test",
        persistence_dir="/tmp/test/.state",
        agent=agent,
    )

    # Set up filestore
    state._fs = InMemoryFileStore()

    return state


def test_create_event_with_key_value():
    """Test creating ConversationStateUpdateEvent with key-value pair."""
    event = ConversationStateUpdateEvent(
        key="agent_status", value=AgentExecutionStatus.RUNNING.value
    )

    assert event.key == "agent_status"
    assert event.value == AgentExecutionStatus.RUNNING.value


def test_create_event_with_full_state():
    """Test creating ConversationStateUpdateEvent with full state snapshot."""
    state_snapshot = {
        "agent_status": "running",
        "confirmation_policy": {"kind": "NeverConfirm"},
        "activated_knowledge_microagents": [],
        "stats": {"service_to_metrics": {}},
    }

    event = ConversationStateUpdateEvent(key="full_state", value=state_snapshot)

    assert event.key == "full_state"
    assert event.value == state_snapshot


def test_validate_key_allows_arbitrary_keys():
    """Test that validator allows arbitrary string keys for flexibility."""
    # We allow arbitrary keys for testing and future extensibility
    event = ConversationStateUpdateEvent(key="custom_field", value="test")
    assert event.key == "custom_field"


def test_validate_key_allows_full_state():
    """Test that validator allows the special 'full_state' key."""
    event = ConversationStateUpdateEvent(key="full_state", value={})
    assert event.key == "full_state"


def test_validate_key_allows_valid_state_fields():
    """Test that validator allows valid ConversationState fields."""
    # Test some valid fields
    valid_keys = ["agent_status", "max_iterations", "stuck_detection"]

    for key in valid_keys:
        event = ConversationStateUpdateEvent(key=key, value="test_value")
        assert event.key == key


def test_from_conversation_state_creates_full_snapshot(state):
    """Test that from_conversation_state creates a full state snapshot."""
    event = ConversationStateUpdateEvent.from_conversation_state(state)

    assert event.key == "full_state"
    assert isinstance(event.value, dict)
    assert "agent_status" in event.value
    assert "confirmation_policy" in event.value
    assert "activated_knowledge_microagents" in event.value
    assert "agent" in event.value
    assert "stats" in event.value


def test_from_conversation_state_serializes_agent_status(state):
    """Test that agent_status is properly serialized."""
    with state:
        state.agent_status = AgentExecutionStatus.RUNNING

    event = ConversationStateUpdateEvent.from_conversation_state(state)

    assert event.value["agent_status"] == "running"


def test_from_conversation_state_serializes_confirmation_policy(state):
    """Test that confirmation_policy is properly serialized."""
    with state:
        state.confirmation_policy = NeverConfirm()

    event = ConversationStateUpdateEvent.from_conversation_state(state)

    assert event.value["confirmation_policy"] == {"kind": "NeverConfirm"}


def test_from_conversation_state_serializes_agent(state):
    """Test that agent configuration is properly serialized."""
    event = ConversationStateUpdateEvent.from_conversation_state(state)

    assert "agent" in event.value
    agent_data = event.value["agent"]
    assert isinstance(agent_data, dict)
    assert "llm" in agent_data
    # Check that SecretStr fields are properly serialized
    assert isinstance(agent_data["llm"], dict)


def test_event_can_be_json_serialized(state):
    """Test that event can be serialized to JSON (important for WebSocket)."""
    event = ConversationStateUpdateEvent.from_conversation_state(state)

    # This should not raise
    event_dict = event.model_dump()
    json_str = json.dumps(event_dict)

    # Verify we can deserialize
    parsed = json.loads(json_str)
    assert parsed["key"] == "full_state"
    assert isinstance(parsed["value"], dict)


def test_event_str_representation():
    """Test the string representation of the event."""
    event = ConversationStateUpdateEvent(key="agent_status", value="running")

    str_repr = str(event)
    assert "ConversationStateUpdate" in str_repr
    assert "agent_status" in str_repr
    assert "running" in str_repr


def test_event_with_complex_nested_values(state):
    """Test event handles complex nested values in agent config."""
    event = ConversationStateUpdateEvent.from_conversation_state(state)

    # Verify nested structures are preserved
    assert "stats" in event.value
    stats = event.value["stats"]
    assert isinstance(stats, dict)


def test_event_immutability():
    """Test that ConversationStateUpdateEvent is immutable like other events."""
    event = ConversationStateUpdateEvent(key="agent_status", value="running")

    # Should not be able to modify fields
    with pytest.raises(Exception):  # Pydantic raises ValidationError or similar
        event.key = "new_key"


def test_event_includes_standard_event_fields():
    """Test that event includes standard EventBase fields."""
    event = ConversationStateUpdateEvent(key="agent_status", value="running")

    # Should have standard event fields from EventBase
    assert hasattr(event, "kind")
    assert hasattr(event, "id")
    assert hasattr(event, "timestamp")
    assert event.kind == "ConversationStateUpdateEvent"


def test_multiple_events_have_unique_ids():
    """Test that multiple events get unique IDs."""
    event1 = ConversationStateUpdateEvent(key="agent_status", value="running")
    event2 = ConversationStateUpdateEvent(key="agent_status", value="running")

    assert event1.id != event2.id


def test_event_timestamp_is_set():
    """Test that event timestamp is automatically set."""
    from datetime import datetime

    before = datetime.now()
    event = ConversationStateUpdateEvent(key="agent_status", value="running")
    after = datetime.now()

    # Timestamp should be within reasonable range
    # Parse the ISO format timestamp string
    event_time = datetime.fromisoformat(event.timestamp)
    assert before <= event_time <= after
