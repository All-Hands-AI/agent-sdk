"""Tests for ConversationStateUpdateEvent."""

import pytest

from openhands.sdk.event.conversation_state import ConversationStateUpdateEvent


def test_conversation_state_update_event_creation():
    """Test that ConversationStateUpdateEvent can be created successfully."""
    event = ConversationStateUpdateEvent(
        agent_status="idle",
        confirmation_policy={"type": "NeverConfirm"},
        activated_knowledge_microagents=[],
        agent={"llm": {"model": "gpt-4"}},
        stats={"total_cost": 0.0},
    )

    assert event.agent_status == "idle"
    assert event.confirmation_policy == {"type": "NeverConfirm"}
    assert event.activated_knowledge_microagents == []
    assert event.agent == {"llm": {"model": "gpt-4"}}
    assert event.stats == {"total_cost": 0.0}


def test_conversation_state_update_event_serialization():
    """Test that ConversationStateUpdateEvent can be serialized and deserialized."""
    event = ConversationStateUpdateEvent(
        agent_status="running",
        confirmation_policy={"type": "AlwaysConfirm"},
        activated_knowledge_microagents=["test-agent"],
        agent={"llm": {"model": "gpt-3.5"}},
        stats={"total_cost": 1.5},
    )

    # Test serialization
    serialized = event.model_dump()
    assert serialized["agent_status"] == "running"
    assert serialized["confirmation_policy"] == {"type": "AlwaysConfirm"}
    assert serialized["activated_knowledge_microagents"] == ["test-agent"]

    # Test deserialization
    deserialized = ConversationStateUpdateEvent.model_validate(serialized)
    assert deserialized.agent_status == "running"
    assert deserialized.confirmation_policy == {"type": "AlwaysConfirm"}
    assert deserialized.activated_knowledge_microagents == ["test-agent"]


def test_conversation_state_update_event_with_complex_data():
    """Test ConversationStateUpdateEvent with more complex data structures."""
    event = ConversationStateUpdateEvent(
        agent_status="paused",
        confirmation_policy={
            "type": "CustomConfirm",
            "settings": {"timeout": 30, "auto_approve": False},
        },
        activated_knowledge_microagents=["agent1", "agent2", "agent3"],
        agent={
            "llm": {"model": "gpt-4", "temperature": 0.7},
            "tools": ["bash", "editor"],
            "config": {"max_iterations": 10},
        },
        stats={
            "total_cost": 2.5,
            "tokens_used": 1500,
            "api_calls": 5,
            "duration": 120.5,
        },
    )

    assert event.agent_status == "paused"
    assert event.confirmation_policy["type"] == "CustomConfirm"
    assert event.confirmation_policy["settings"]["timeout"] == 30
    assert len(event.activated_knowledge_microagents) == 3
    assert event.agent["llm"]["temperature"] == 0.7
    assert event.stats["tokens_used"] == 1500


def test_conversation_state_update_event_immutability():
    """Test that ConversationStateUpdateEvent is immutable."""
    event = ConversationStateUpdateEvent(
        agent_status="idle",
        confirmation_policy={"type": "NeverConfirm"},
        activated_knowledge_microagents=[],
        agent={"llm": {"model": "gpt-4"}},
        stats={"total_cost": 0.0},
    )

    # Try to modify the event - should raise an error
    with pytest.raises(Exception):  # Pydantic frozen model should prevent modification
        event.agent_status = "running"
