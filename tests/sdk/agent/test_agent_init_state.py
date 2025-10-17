"""Tests for Agent.init_state modifying state in-place."""

import tempfile
import uuid

from pydantic import SecretStr

from openhands.sdk.agent import Agent
from openhands.sdk.conversation.state import ConversationState
from openhands.sdk.event import SystemPromptEvent
from openhands.sdk.llm import LLM, TextContent
from openhands.sdk.workspace import LocalWorkspace


def test_init_state_modifies_state_in_place():
    """Test that init_state modifies state in-place by adding SystemPromptEvent."""
    llm = LLM(
        model="gpt-4o-mini",
        api_key=SecretStr("test-key"),
        service_id="test-llm",
    )
    agent = Agent(llm=llm, tools=[])

    # Create a conversation state using the factory method
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = LocalWorkspace(working_dir=tmpdir)
        state = ConversationState.create(
            id=uuid.uuid4(),
            agent=agent,
            workspace=workspace,
            persistence_dir=tmpdir,
        )

        # Capture events added via on_event callback
        captured_events = []

        def on_event(event):
            captured_events.append(event)
            state.events.append(event)

        # Get initial event count
        initial_event_count = len(state.events)

        # Call init_state
        agent.init_state(state, on_event=on_event)

        # Verify that init_state modified the state in-place
        # by adding a SystemPromptEvent (since there were no LLMConvertibleEvents initially)
        assert len(state.events) > initial_event_count, (
            "init_state should have added events to the state"
        )

        # Verify that a SystemPromptEvent was added
        system_prompt_events = [
            e for e in state.events if isinstance(e, SystemPromptEvent)
        ]
        assert len(system_prompt_events) > 0, (
            "init_state should have added a SystemPromptEvent"
        )

        # Verify that the same event was captured in the callback
        assert len(captured_events) > 0, (
            "init_state should have called on_event callback"
        )
        assert isinstance(captured_events[0], SystemPromptEvent), (
            "First captured event should be SystemPromptEvent"
        )


def test_init_state_initializes_agent_tools():
    """Test that init_state initializes agent tools via _initialize."""
    llm = LLM(
        model="gpt-4o-mini",
        api_key=SecretStr("test-key"),
        service_id="test-llm",
    )
    agent = Agent(llm=llm, tools=[])

    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = LocalWorkspace(working_dir=tmpdir)
        state = ConversationState.create(
            id=uuid.uuid4(),
            agent=agent,
            workspace=workspace,
            persistence_dir=tmpdir,
        )

        captured_events = []

        def on_event(event):
            captured_events.append(event)
            state.events.append(event)

        # Verify tools are not initialized before init_state
        assert not agent._tools, "Tools should not be initialized before init_state"

        # Call init_state
        agent.init_state(state, on_event=on_event)

        # Verify tools are initialized after init_state
        assert agent._tools, "Tools should be initialized after init_state"
        assert "finish" in agent.tools_map, "Built-in finish tool should be present"
        assert "think" in agent.tools_map, "Built-in think tool should be present"


def test_init_state_does_not_add_duplicate_system_prompt():
    """Test that init_state doesn't add SystemPromptEvent if LLMConvertibleEvents exist."""
    llm = LLM(
        model="gpt-4o-mini",
        api_key=SecretStr("test-key"),
        service_id="test-llm",
    )
    agent = Agent(llm=llm, tools=[])

    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = LocalWorkspace(working_dir=tmpdir)
        state = ConversationState.create(
            id=uuid.uuid4(),
            agent=agent,
            workspace=workspace,
            persistence_dir=tmpdir,
        )

        # Add a SystemPromptEvent first
        initial_system_prompt = SystemPromptEvent(
            source="agent",
            system_prompt=TextContent(text="Initial system prompt"),
            tools=[],
        )
        state.events.append(initial_system_prompt)

        captured_events = []

        def on_event(event):
            captured_events.append(event)
            state.events.append(event)

        initial_event_count = len(state.events)

        # Call init_state
        agent.init_state(state, on_event=on_event)

        # Verify that init_state did NOT add another SystemPromptEvent
        # (because one already exists)
        assert len(state.events) == initial_event_count, (
            "init_state should not add SystemPromptEvent when LLMConvertibleEvents already exist"
        )
        assert len(captured_events) == 0, (
            "init_state should not call on_event when LLMConvertibleEvents already exist"
        )


def test_init_state_with_id_preservation():
    """Test that init_state preserves the state's identity."""
    llm = LLM(
        model="gpt-4o-mini",
        api_key=SecretStr("test-key"),
        service_id="test-llm",
    )
    agent = Agent(llm=llm, tools=[])

    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = LocalWorkspace(working_dir=tmpdir)
        state_id = uuid.uuid4()
        state = ConversationState.create(
            id=state_id,
            agent=agent,
            workspace=workspace,
            persistence_dir=tmpdir,
        )

        captured_events = []

        def on_event(event):
            captured_events.append(event)
            state.events.append(event)

        # Store the original state object reference
        original_state_id = id(state)

        # Call init_state
        agent.init_state(state, on_event=on_event)

        # Verify that the state object is the same (in-place modification)
        assert id(state) == original_state_id, (
            "init_state should modify the same state object in-place"
        )
        assert state.id == state_id, "State ID should be preserved"
