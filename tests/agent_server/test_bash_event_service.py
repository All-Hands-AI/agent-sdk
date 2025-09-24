"""Tests for BashEventService."""

import asyncio
import tempfile
from pathlib import Path

import pytest

from openhands.agent_server.bash_service import BashEventService
from openhands.agent_server.models import BashCommand, BashOutput
from openhands.agent_server.pub_sub import Subscriber


@pytest.fixture
def bash_event_service():
    """Create a BashEventService instance for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        yield BashEventService(
            working_dir=temp_path / "workspace",
            bash_events_dir=temp_path / "bash_events",
        )


@pytest.mark.asyncio
async def test_start_bash_command(bash_event_service):
    """Test starting a bash command."""
    command = BashCommand(command='echo "Hello World"', cwd="/tmp")

    # This should not raise an exception
    await bash_event_service.start_bash_command(command)

    # Wait a bit for the command to complete
    await asyncio.sleep(1)

    # Verify the command was saved to file
    retrieved = await bash_event_service.get_bash_event(command.id.hex)
    assert retrieved is not None
    assert retrieved.id == command.id
    assert retrieved.command == 'echo "Hello World"'


@pytest.mark.asyncio
async def test_get_bash_event(bash_event_service):
    """Test getting a bash event by ID."""
    command = BashCommand(command='echo "test"', cwd="/tmp")
    await bash_event_service.start_bash_command(command)

    # Wait for command to complete
    await asyncio.sleep(1)

    retrieved = await bash_event_service.get_bash_event(command.id.hex)
    assert retrieved is not None
    assert retrieved.id == command.id


@pytest.mark.asyncio
async def test_batch_get_bash_events(bash_event_service):
    """Test batch getting bash events."""
    command = BashCommand(command='echo "batch test"', cwd="/tmp")
    await bash_event_service.start_bash_command(command)

    # Wait for command to complete
    await asyncio.sleep(1)

    results = await bash_event_service.batch_get_bash_events([command.id.hex])
    assert len(results) == 1
    assert results[0] is not None
    assert results[0].id == command.id


@pytest.mark.asyncio
async def test_subscribe_to_events(bash_event_service):
    """Test subscribing to bash events."""
    events_received = []

    class TestSubscriber(Subscriber):
        async def __call__(self, event):
            events_received.append(event)

    subscriber = TestSubscriber()
    subscription_id = await bash_event_service.subscribe_to_events(subscriber)

    # Start a command
    command = BashCommand(command='echo "subscription test"', cwd="/tmp")
    await bash_event_service.start_bash_command(command)

    # Wait for events to be published
    await asyncio.sleep(2)

    # Should have received both command and output events
    assert len(events_received) >= 2
    assert any(isinstance(e, BashCommand) for e in events_received)
    assert any(isinstance(e, BashOutput) for e in events_received)

    # Unsubscribe
    result = await bash_event_service.unsubscribe_from_events(subscription_id)
    assert result is True
