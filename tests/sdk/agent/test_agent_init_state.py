"""Tests for Agent.init_state method to verify in-place state modification."""

import tempfile
import uuid
from collections.abc import Sequence

import pytest
from pydantic import SecretStr

from openhands.sdk import LLM, Agent
from openhands.sdk.conversation.state import ConversationState
from openhands.sdk.event import Event, SystemPromptEvent
from openhands.sdk.llm.message import ImageContent, TextContent
from openhands.sdk.tool import Tool, ToolDefinition
from openhands.sdk.tool.registry import register_tool
from openhands.sdk.tool.tool import Action, Observation, ToolExecutor
from openhands.sdk.workspace import LocalWorkspace


# Test tool for the tests
class _TestAction(Action):
    text: str


class _TestObs(Observation):
    out: str

    @property
    def to_llm_content(self) -> Sequence[TextContent | ImageContent]:
        return [TextContent(text=self.out)]


class _TestExecutor(ToolExecutor[_TestAction, _TestObs]):
    def __call__(self, action: _TestAction) -> _TestObs:
        return _TestObs(out=action.text.upper())


def _make_test_tool(conv_state=None, **kwargs) -> Sequence[ToolDefinition]:
    return [
        ToolDefinition(
            name="test_tool",
            description="Test tool",
            action_type=_TestAction,
            observation_type=_TestObs,
            executor=_TestExecutor(),
        )
    ]


@pytest.fixture
def agent():
    """Create a test agent with a test tool."""
    # Register test tool
    register_tool("test_tool", _make_test_tool)
    
    llm = LLM(model="gpt-4", api_key=SecretStr("test-key"), service_id="test-llm")
    return Agent(llm=llm, tools=[Tool(name="test_tool")])


def test_init_state_modifies_state_in_place(agent):
    """Test that init_state modifies the state object in-place."""
    with tempfile.TemporaryDirectory() as temp_dir:
        state = ConversationState.create(
            id=uuid.uuid4(),
            agent=agent,
            workspace=LocalWorkspace(working_dir=temp_dir),
            persistence_dir=None,
        )
        
        # Capture the original object ID
        original_state_id = id(state)
        original_events_id = id(state.events)
        initial_event_count = len(state.events)
        
        # Track events via callback
        captured_events = []
        
        def on_event(event: Event):
            captured_events.append(event)
            state.events.append(event)
        
        # Call init_state - this should modify state in-place
        agent.init_state(state, on_event=on_event)
        
        # Verify state object is the same (modified in-place)
        assert id(state) == original_state_id, "State object should be modified in-place"
        assert id(state.events) == original_events_id, "Events list should be the same object"
        
        # Verify that events were added
        assert len(state.events) > initial_event_count, "Events should be added to state"


def test_init_state_initializes_tools():
    """Test that init_state initializes agent tools."""
    # Register test tool
    register_tool("test_tool", _make_test_tool)
    
    llm = LLM(model="gpt-4", api_key=SecretStr("test-key"), service_id="test-llm")
    agent = Agent(llm=llm, tools=[Tool(name="test_tool")])
    
    # Before init_state, tools should not be initialized
    with pytest.raises(RuntimeError, match="Agent not initialized"):
        _ = agent.tools_map
    
    with tempfile.TemporaryDirectory() as temp_dir:
        state = ConversationState.create(
            id=uuid.uuid4(),
            agent=agent,
            workspace=LocalWorkspace(working_dir=temp_dir),
            persistence_dir=None,
        )
        
        def on_event(event: Event):
            state.events.append(event)
        
        # Call init_state
        agent.init_state(state, on_event=on_event)
        
        # After init_state, tools should be accessible
        tools = agent.tools_map
        assert "test_tool" in tools, "Test tool should be initialized"
        assert "finish" in tools, "Built-in finish tool should be available"
        assert "think" in tools, "Built-in think tool should be available"


def test_init_state_adds_system_prompt_event():
    """Test that init_state adds a SystemPromptEvent when no LLM messages exist."""
    # Register test tool
    register_tool("test_tool", _make_test_tool)
    
    llm = LLM(model="gpt-4", api_key=SecretStr("test-key"), service_id="test-llm")
    agent = Agent(llm=llm, tools=[Tool(name="test_tool")])
    
    with tempfile.TemporaryDirectory() as temp_dir:
        state = ConversationState.create(
            id=uuid.uuid4(),
            agent=agent,
            workspace=LocalWorkspace(working_dir=temp_dir),
            persistence_dir=None,
        )
        
        captured_events = []
        
        def on_event(event: Event):
            captured_events.append(event)
            state.events.append(event)
        
        # Verify no events initially
        assert len(state.events) == 0
        
        # Call init_state
        agent.init_state(state, on_event=on_event)
        
        # Verify SystemPromptEvent was added
        assert len(captured_events) == 1, "Should have one event"
        assert isinstance(captured_events[0], SystemPromptEvent), "Event should be SystemPromptEvent"
        
        # Verify the event is in state.events
        assert len(state.events) == 1, "State should have one event"
        assert isinstance(state.events[0], SystemPromptEvent), "State event should be SystemPromptEvent"


def test_init_state_does_not_add_system_prompt_if_messages_exist():
    """Test that init_state doesn't add SystemPromptEvent if LLM messages already exist."""
    # Register test tool
    register_tool("test_tool", _make_test_tool)
    
    llm = LLM(model="gpt-4", api_key=SecretStr("test-key"), service_id="test-llm")
    agent = Agent(llm=llm, tools=[Tool(name="test_tool")])
    
    with tempfile.TemporaryDirectory() as temp_dir:
        state = ConversationState.create(
            id=uuid.uuid4(),
            agent=agent,
            workspace=LocalWorkspace(working_dir=temp_dir),
            persistence_dir=None,
        )
        
        # First initialization
        first_captured_events = []
        
        def on_event_first(event: Event):
            first_captured_events.append(event)
            state.events.append(event)
        
        # First call to init_state
        agent.init_state(state, on_event=on_event_first)
        
        # Should have one SystemPromptEvent
        assert len(state.events) == 1
        assert isinstance(state.events[0], SystemPromptEvent)
        
        # Second initialization with same state
        second_captured_events = []
        
        def on_event_second(event: Event):
            second_captured_events.append(event)
            state.events.append(event)
        
        # Second call to init_state - should not add another SystemPromptEvent
        agent.init_state(state, on_event=on_event_second)
        
        # Should still have only one event (not duplicated)
        assert len(second_captured_events) == 0, "Should not add another SystemPromptEvent"
        assert len(state.events) == 1, "State should still have only one event"


def test_init_state_state_events_persistence():
    """Test that events added during init_state persist in the state."""
    # Register test tool
    register_tool("test_tool", _make_test_tool)
    
    llm = LLM(model="gpt-4", api_key=SecretStr("test-key"), service_id="test-llm")
    agent = Agent(llm=llm, tools=[Tool(name="test_tool")])
    
    with tempfile.TemporaryDirectory() as temp_dir:
        state = ConversationState.create(
            id=uuid.uuid4(),
            agent=agent,
            workspace=LocalWorkspace(working_dir=temp_dir),
            persistence_dir=None,
        )
        
        def on_event(event: Event):
            state.events.append(event)
        
        # Get initial event count
        initial_count = len(state.events)
        
        # Call init_state
        agent.init_state(state, on_event=on_event)
        
        # Verify event was actually added to the state
        assert len(state.events) == initial_count + 1, "Event should be added to state"
        
        # Verify we can access the event after init_state completes
        added_event = state.events[-1]
        assert isinstance(added_event, SystemPromptEvent), "Last event should be SystemPromptEvent"
        assert added_event.source == "agent", "Event source should be 'agent'"
