"""Tests for BashTaskService."""

import asyncio
from pathlib import Path

import pytest

from openhands.agent_server.bash_task_service import BashTaskService
from openhands.agent_server.models import ActionEvent, ObservationEvent
from openhands.tools.execute_bash.definition import ExecuteBashAction


@pytest.fixture
def bash_task_service():
    """Create a BashTaskService instance for testing."""
    return BashTaskService(working_dir=Path.cwd())


@pytest.mark.asyncio
async def test_start_bash_task(bash_task_service):
    """Test starting a bash task."""
    action = ExecuteBashAction(command='echo "Hello World"')
    event = await bash_task_service.start_bash_task(action)

    assert isinstance(event, ActionEvent)
    assert isinstance(event.action, ExecuteBashAction)
    assert event.action.command == 'echo "Hello World"'
    assert event.tool_name == "execute_bash"


@pytest.mark.asyncio
async def test_get_event(bash_task_service):
    """Test getting an event by ID."""
    action = ExecuteBashAction(command='echo "test"')
    event = await bash_task_service.start_bash_task(action)

    retrieved = await bash_task_service.get_event(event.id)
    assert retrieved is not None
    assert retrieved.id == event.id


@pytest.mark.asyncio
async def test_batch_get_events(bash_task_service):
    """Test batch getting events."""
    action = ExecuteBashAction(command='echo "batch test"')
    event = await bash_task_service.start_bash_task(action)

    results = await bash_task_service.batch_get_events([event.id])
    assert len(results) == 1
    assert results[0] is not None
    assert results[0].id == event.id


@pytest.mark.asyncio
async def test_search_events(bash_task_service):
    """Test searching events."""
    action = ExecuteBashAction(command='echo "search test"')
    event = await bash_task_service.start_bash_task(action)

    # Wait a moment for execution to complete
    await asyncio.sleep(0.5)

    # Search all events
    results = await bash_task_service.search_events()
    assert len(results.items) >= 1

    # Search by action ID
    action_results = await bash_task_service.search_events(action_id=event.id)
    assert len(action_results.items) >= 1

    # Should have both action and observation events
    action_events = [e for e in action_results.items if isinstance(e, ActionEvent)]
    observation_events = [
        e for e in action_results.items if isinstance(e, ObservationEvent)
    ]

    assert len(action_events) == 1
    assert len(observation_events) >= 1  # At least one observation


@pytest.mark.asyncio
async def test_subscribe_to_events(bash_task_service):
    """Test subscribing to events."""
    events_received = []

    class TestSubscriber:
        async def __call__(self, event):
            events_received.append(event)

    subscriber = TestSubscriber()
    subscription_id = await bash_task_service.subscribe_to_events(subscriber)

    # Start a task
    action = ExecuteBashAction(command='echo "subscription test"')
    await bash_task_service.start_bash_task(action)

    # Wait for events to be published
    await asyncio.sleep(0.5)

    # Should have received at least the action event
    assert len(events_received) >= 1
    assert any(isinstance(e, ActionEvent) for e in events_received)

    # Unsubscribe
    await bash_task_service.unsubscribe_from_events(subscription_id)
