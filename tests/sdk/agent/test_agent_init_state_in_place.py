"""Test that Agent.init_state modifies state in-place."""

import tempfile
import uuid

from pydantic import SecretStr

from openhands.sdk.agent import Agent
from openhands.sdk.conversation import ConversationState
from openhands.sdk.event import SystemPromptEvent
from openhands.sdk.llm import LLM
from openhands.sdk.workspace import LocalWorkspace


def test_init_state_modifies_state_in_place():
    """Test that init_state modifies the state object in-place.
    
    This test verifies that:
    1. The state object passed to init_state is the same object after the call
    2. The state's events list is modified through the on_event callback
    3. A SystemPromptEvent is added when there are no LLM convertible messages
    """
    # Create test agent
    llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="test-llm")
    agent = Agent(llm=llm, tools=[])

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a fresh state with no events
        workspace = LocalWorkspace(working_dir=tmpdir)
        state = ConversationState.create(
            id=uuid.uuid4(),
            agent=agent,
            workspace=workspace,
            persistence_dir=tmpdir,
        )
        
        # Store the object ID before init_state
        state_id_before = id(state)
        events_id_before = id(state.events)
        initial_event_count = len(state.events)
        
        # Track events added via callback
        added_events = []
        
        def on_event_callback(event):
            added_events.append(event)
            state.events.append(event)
        
        # Call init_state
        agent.init_state(state, on_event=on_event_callback)
        
        # Verify state object is the same (modified in-place)
        state_id_after = id(state)
        assert state_id_before == state_id_after, (
            "init_state should modify state in-place, not create a new object"
        )
        
        # Verify events list is the same object (modified in-place)
        events_id_after = id(state.events)
        assert events_id_before == events_id_after, (
            "init_state should modify the events list in-place"
        )
        
        # Verify that on_event was called (events were added)
        assert len(added_events) > 0, (
            "init_state should call on_event to add events"
        )
        
        # Verify state.events was modified
        assert len(state.events) > initial_event_count, (
            "init_state should add events to the state"
        )
        
        # Verify a SystemPromptEvent was added (since we started with no messages)
        system_prompt_events = [
            e for e in added_events if isinstance(e, SystemPromptEvent)
        ]
        assert len(system_prompt_events) == 1, (
            "init_state should add exactly one SystemPromptEvent when there are no "
            "LLM convertible messages"
        )
        
        # Verify the SystemPromptEvent contains tools
        system_prompt_event = system_prompt_events[0]
        assert system_prompt_event.tools is not None, (
            "SystemPromptEvent should contain tools"
        )
        assert len(system_prompt_event.tools) > 0, (
            "SystemPromptEvent should contain at least the built-in tools"
        )
        
        # Verify the system prompt is populated
        assert system_prompt_event.system_prompt is not None, (
            "SystemPromptEvent should contain a system prompt"
        )


def test_init_state_does_not_add_duplicate_system_prompt():
    """Test that init_state doesn't add a SystemPromptEvent if one already exists.
    
    This test verifies that when the state already has LLM convertible messages,
    init_state doesn't add another SystemPromptEvent.
    """
    # Create test agent
    llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="test-llm")
    agent = Agent(llm=llm, tools=[])

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a fresh state
        workspace = LocalWorkspace(working_dir=tmpdir)
        state = ConversationState.create(
            id=uuid.uuid4(),
            agent=agent,
            workspace=workspace,
            persistence_dir=tmpdir,
        )
        
        # Track events added via callback
        added_events_first = []
        
        def on_event_callback_first(event):
            added_events_first.append(event)
            state.events.append(event)
        
        # Call init_state first time (should add SystemPromptEvent)
        agent.init_state(state, on_event=on_event_callback_first)
        
        # Count initial SystemPromptEvents
        initial_system_prompts = [
            e for e in state.events if isinstance(e, SystemPromptEvent)
        ]
        initial_count = len(initial_system_prompts)
        assert initial_count > 0, "First init_state should add a SystemPromptEvent"
        
        # Track events added in second call
        added_events_second = []
        
        def on_event_callback_second(event):
            added_events_second.append(event)
            state.events.append(event)
        
        # Call init_state again (should NOT add another SystemPromptEvent)
        agent.init_state(state, on_event=on_event_callback_second)
        
        # Count SystemPromptEvents after second init_state
        final_system_prompts = [
            e for e in state.events if isinstance(e, SystemPromptEvent)
        ]
        final_count = len(final_system_prompts)
        
        # Should not have added another SystemPromptEvent
        assert final_count == initial_count, (
            "init_state should not add a SystemPromptEvent when LLM convertible "
            "messages already exist"
        )
        
        # Verify no events were added in the second call
        assert len(added_events_second) == 0, (
            "init_state should not add events when state already has LLM "
            "convertible messages"
        )


def test_init_state_preserves_state_attributes():
    """Test that init_state modifies state in-place and preserves attributes.
    
    This test verifies that init_state modifies the state without replacing
    any of its core attributes like workspace, agent_status, etc.
    """
    # Create test agent
    llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="test-llm")
    agent = Agent(llm=llm, tools=[])

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a fresh state
        workspace = LocalWorkspace(working_dir=tmpdir)
        state = ConversationState.create(
            id=uuid.uuid4(),
            agent=agent,
            workspace=workspace,
            persistence_dir=tmpdir,
        )
        
        # Store references to state attributes before init_state
        workspace_before = state.workspace
        workspace_id_before = id(state.workspace)
        agent_status_before = state.agent_status
        persistence_dir_before = state.persistence_dir
        
        # Track events
        added_events = []
        
        def on_event_callback(event):
            added_events.append(event)
            state.events.append(event)
        
        # Call init_state
        agent.init_state(state, on_event=on_event_callback)
        
        # Verify state attributes are preserved (same objects, not replaced)
        assert state.workspace is workspace_before, (
            "init_state should not replace the workspace attribute"
        )
        assert id(state.workspace) == workspace_id_before, (
            "init_state should not create a new workspace object"
        )
        assert state.agent_status == agent_status_before, (
            "init_state should preserve agent_status"
        )
        assert state.persistence_dir == persistence_dir_before, (
            "init_state should preserve persistence_dir"
        )
        
        # Verify that events were added (state was modified)
        assert len(added_events) > 0, (
            "init_state should add events through the callback"
        )
