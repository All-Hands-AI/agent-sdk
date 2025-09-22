"""Tests for workspace service."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openhands.agent_server.config import Config
from openhands.agent_server.workspace_service import BashEvent, WorkspaceService
from openhands.tools.execute_bash import ExecuteBashAction, ExecuteBashObservation


@pytest.fixture
def temp_config():
    """Create a temporary config for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config = Config(
            workspace_path=Path(temp_dir) / "workspace",
            bash_events_path=Path(temp_dir) / "bash_events.json",
        )
        config.workspace_path.mkdir(parents=True, exist_ok=True)
        yield config


@pytest.fixture
def workspace_service(temp_config):
    """Create a workspace service for testing."""
    service = WorkspaceService(config=temp_config)
    yield service
    # Cleanup
    asyncio.run(service.close())


def test_workspace_service_initialization(temp_config):
    """Test workspace service initialization."""
    service = WorkspaceService(config=temp_config)

    assert service.config == temp_config
    assert service._bash_executor is None
    assert service._events == []
    assert service._pub_sub is not None


def test_bash_event_creation():
    """Test BashEvent creation and serialization."""
    action = ExecuteBashAction(command="echo hello")
    observation = ExecuteBashObservation(
        output="hello\n", exit_code=0, error=False, timeout=False
    )

    event = BashEvent(action=action, observation=observation)

    assert event.action == action
    assert event.observation == observation
    assert event.id is not None
    assert event.timestamp is not None
    assert event.source == "agent"

    # Test serialization
    event_dict = event.to_dict()
    assert "id" in event_dict
    assert "timestamp" in event_dict
    assert "source" in event_dict
    assert "action" in event_dict
    assert "observation" in event_dict
    assert event_dict["action"]["command"] == "echo hello"
    assert event_dict["observation"]["output"] == "hello\n"


@pytest.mark.asyncio
async def test_execute_bash_command(workspace_service):
    """Test bash command execution."""
    action = ExecuteBashAction(command="echo test")

    with patch.object(workspace_service, "_get_bash_executor") as mock_get_executor:
        mock_executor = MagicMock()
        mock_get_executor.return_value = mock_executor

        # Mock the executor call
        mock_observation = ExecuteBashObservation(
            output="test\n", exit_code=0, error=False, timeout=False
        )
        mock_executor.return_value = mock_observation

        # Execute the command
        result = await workspace_service.execute_bash_command(action)

        assert result == mock_observation
        assert len(workspace_service._events) == 1

        event = workspace_service._events[0]
        assert event.action == action
        assert event.observation == mock_observation


def test_search_events(workspace_service):
    """Test event searching functionality."""
    # Add some test events
    action1 = ExecuteBashAction(command="echo hello")
    action2 = ExecuteBashAction(command="ls -la")

    event1 = BashEvent(action=action1)
    event2 = BashEvent(action=action2)

    workspace_service._events = [event1, event2]

    # Test search without filter
    events = workspace_service.search_events(limit=10, offset=0)
    assert len(events) == 2

    # Test search with filter
    events = workspace_service.search_events(limit=10, offset=0, command_filter="echo")
    assert len(events) == 1
    assert events[0].action.command == "echo hello"

    # Test pagination
    events = workspace_service.search_events(limit=1, offset=0)
    assert len(events) == 1

    events = workspace_service.search_events(limit=1, offset=1)
    assert len(events) == 1


def test_get_event(workspace_service):
    """Test getting a specific event by ID."""
    action = ExecuteBashAction(command="echo test")
    event = BashEvent(action=action)

    workspace_service._events = [event]

    # Test getting existing event
    retrieved_event = workspace_service.get_event(event.id)
    assert retrieved_event == event

    # Test getting non-existent event
    retrieved_event = workspace_service.get_event("non-existent-id")
    assert retrieved_event is None


def test_count_events(workspace_service):
    """Test event counting functionality."""
    action1 = ExecuteBashAction(command="echo hello")
    action2 = ExecuteBashAction(command="ls -la")

    event1 = BashEvent(action=action1)
    event2 = BashEvent(action=action2)

    workspace_service._events = [event1, event2]

    # Test count without filter
    count = workspace_service.count_events()
    assert count == 2

    # Test count with filter
    count = workspace_service.count_events(command_filter="echo")
    assert count == 1


def test_save_and_load_events(temp_config):
    """Test event persistence."""
    service = WorkspaceService(config=temp_config)

    action = ExecuteBashAction(command="echo test")
    event = BashEvent(action=action)

    service._events = [event]
    service._save_events()

    # Verify file was created
    events_file = Path(temp_config.bash_events_path)
    assert events_file.exists()

    # Load events in a new service instance
    new_service = WorkspaceService(config=temp_config)
    assert len(new_service._events) == 1

    loaded_event = new_service._events[0]
    assert loaded_event.action.command == "echo test"


@pytest.mark.asyncio
async def test_pub_sub_notification(workspace_service):
    """Test that events are published to subscribers."""
    mock_subscriber = AsyncMock()
    workspace_service._pub_sub.subscribe(mock_subscriber)

    action = ExecuteBashAction(command="echo test")

    with patch.object(workspace_service, "_get_bash_executor") as mock_get_executor:
        mock_executor = MagicMock()
        mock_get_executor.return_value = mock_executor

        mock_observation = ExecuteBashObservation(
            output="test\n", exit_code=0, error=False, timeout=False
        )
        mock_executor.return_value = mock_observation

        await workspace_service.execute_bash_command(action)

        # Verify subscriber was called
        mock_subscriber.assert_called_once()
        called_event = mock_subscriber.call_args[0][0]
        assert isinstance(called_event, BashEvent)
        assert called_event.action == action
        assert called_event.observation == mock_observation


@pytest.mark.asyncio
async def test_service_close():
    """Test service cleanup."""
    # Create a config with webhooks
    from openhands.agent_server.config import Config, WebhookSpec

    webhook_spec = WebhookSpec(
        base_url="http://example.com",
        headers={},
        event_buffer_size=10,
        flush_delay=5.0,
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        config = Config(
            workspace_path=Path(temp_dir) / "workspace",
            bash_events_path=Path(temp_dir) / "bash_events.json",
            webhooks=[webhook_spec],
        )
        config.workspace_path.mkdir(parents=True, exist_ok=True)

        workspace_service = WorkspaceService(config=config)

        # Verify webhook subscriber was created
        assert len(workspace_service._webhook_subscribers) == 1

        # Close the service
        await workspace_service.close()

        # Verify webhook subscribers are cleaned up
        assert len(workspace_service._webhook_subscribers) == 0
