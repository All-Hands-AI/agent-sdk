"""Tests for ToolEventService."""

import asyncio
import tempfile
from pathlib import Path

import pytest

from openhands.agent_server.models import ActionEvent
from openhands.agent_server.tool_event_service import ToolEventService
from openhands.tools.execute_bash.definition import ExecuteBashAction


@pytest.fixture
def tool_event_service():
    """Create a ToolEventService instance for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        yield ToolEventService(
            working_dir=temp_path / "workspace",
            tool_events_dir=temp_path / "tool_events",
        )


@pytest.mark.asyncio
async def test_start_bash_execution(tool_event_service):
    """Test starting a tool event."""
    action = ExecuteBashAction(command='echo "Hello World"')
    event = await tool_event_service.start_bash_execution(action)

    assert isinstance(event, ActionEvent)
    assert isinstance(event.action, ExecuteBashAction)
    assert event.action.command == 'echo "Hello World"'
    assert event.tool_name == "execute_bash"


@pytest.mark.asyncio
async def test_get_event(tool_event_service):
    """Test getting an event by ID."""
    action = ExecuteBashAction(command='echo "test"')
    event = await tool_event_service.start_bash_execution(action)

    retrieved = await tool_event_service.get_event(event.id)
    assert retrieved is not None
    assert retrieved.id == event.id


@pytest.mark.asyncio
async def test_batch_get_events(tool_event_service):
    """Test batch getting events."""
    action = ExecuteBashAction(command='echo "batch test"')
    event = await tool_event_service.start_bash_execution(action)

    results = await tool_event_service.batch_get_events([event.id])
    assert len(results) == 1
    assert results[0] is not None
    assert results[0].id == event.id


@pytest.mark.asyncio
async def test_subscribe_to_events(tool_event_service):
    """Test subscribing to events."""
    events_received = []

    class TestSubscriber:
        async def __call__(self, event):
            events_received.append(event)

    subscriber = TestSubscriber()
    subscription_id = await tool_event_service.subscribe_to_events(subscriber)

    # Start a task
    action = ExecuteBashAction(command='echo "subscription test"')
    await tool_event_service.start_bash_execution(action)

    # Wait for events to be published
    await asyncio.sleep(0.5)

    # Should have received at least the action event
    assert len(events_received) >= 1
    assert any(isinstance(e, ActionEvent) for e in events_received)

    # Unsubscribe
    await tool_event_service.unsubscribe_from_events(subscription_id)
