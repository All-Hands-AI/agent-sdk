"""Tests for workspace router."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from openhands.agent_server.api import create_app
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
            session_api_key=None,  # Disable authentication for tests
        )
        config.workspace_path.mkdir(parents=True, exist_ok=True)
        yield config


@pytest.fixture
def test_client(temp_config):
    """Create a test client with temporary config."""
    # Create app with custom config to bypass authentication
    app = create_app(temp_config)

    with (
        patch(
            "openhands.agent_server.api.get_default_workspace_service"
        ) as mock_service,
        patch("openhands.agent_server.workspace_router.config", temp_config),
        patch("openhands.agent_server.workspace_router.workspace_service"),
    ):
        service = WorkspaceService(config=temp_config)
        mock_service.return_value = service
        # Directly set the workspace_service in the router module
        import openhands.agent_server.workspace_router as router_module

        original_service = router_module.workspace_service
        router_module.workspace_service = service

        try:
            with TestClient(app) as client:
                yield client, service
        finally:
            # Restore original service
            router_module.workspace_service = original_service


def test_upload_file(test_client):
    """Test file upload endpoint."""
    client, service = test_client

    # Create a test file
    test_content = b"Hello, World!"

    response = client.post(
        "/api/workspace/upload",
        files={"file": ("test.txt", test_content, "text/plain")},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["success"] is True

    # Verify file was created
    uploaded_file = service.config.workspace_path / "test.txt"
    assert uploaded_file.exists()
    assert uploaded_file.read_bytes() == test_content


def test_upload_file_with_path(test_client):
    """Test file upload with custom path."""
    client, service = test_client

    test_content = b"Hello, World!"

    response = client.post(
        "/api/workspace/upload?path=subdir/custom.txt",
        files={"file": ("test.txt", test_content, "text/plain")},
    )

    assert response.status_code == 200

    # Verify file was created at custom path
    uploaded_file = service.config.workspace_path / "subdir" / "custom.txt"
    assert uploaded_file.exists()
    assert uploaded_file.read_bytes() == test_content


def test_download_file(test_client):
    """Test file download endpoint."""
    client, service = test_client

    # Create a test file
    test_file = service.config.workspace_path / "download_test.txt"
    test_content = "Hello, Download!"
    test_file.write_text(test_content)

    response = client.get("/api/workspace/download?path=download_test.txt")

    assert response.status_code == 200
    assert response.text == test_content
    assert (
        response.headers["content-disposition"]
        == 'attachment; filename="download_test.txt"'
    )


def test_download_nonexistent_file(test_client):
    """Test downloading a file that doesn't exist."""
    client, service = test_client

    response = client.get("/api/workspace/download?path=nonexistent.txt")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_download_file_outside_workspace(test_client):
    """Test that files outside workspace cannot be downloaded."""
    client, service = test_client

    response = client.get("/api/workspace/download?path=../../../etc/passwd")

    assert response.status_code == 400
    assert "outside workspace" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_execute_bash(test_client):
    """Test bash command execution endpoint."""
    client, service = test_client

    with patch.object(service, "execute_bash_command") as mock_execute:
        mock_observation = ExecuteBashObservation(
            output="Hello, World!\n", exit_code=0, error=False, timeout=False
        )
        mock_execute.return_value = mock_observation

        request_data = ExecuteBashAction(command="echo 'Hello, World!'")

        response = client.post(
            "/api/workspace/execute",
            json=request_data.model_dump(),
        )

        assert response.status_code == 200
        result = response.json()

        assert result["output"] == "Hello, World!\n"
        assert result["exit_code"] == 0
        assert result["error"] is False
        assert result["timeout"] is False

        # Verify the service method was called
        mock_execute.assert_called_once()
        called_action = mock_execute.call_args[0][0]
        assert called_action.command == "echo 'Hello, World!'"


def test_get_bash_events(test_client):
    """Test getting bash events endpoint."""
    client, service = test_client

    # Add some test events
    action1 = ExecuteBashAction(command="echo hello")
    action2 = ExecuteBashAction(command="ls -la")

    event1 = BashEvent(action=action1)
    event2 = BashEvent(action=action2)

    service._events = [event1, event2]

    response = client.get("/api/workspace/bash-events/search")

    assert response.status_code == 200
    result = response.json()

    assert len(result["items"]) == 2  # 2 actions (no observations in test data)
    assert result["next_page_id"] is None

    # Check first item (action)
    first_item = result["items"][0]
    assert first_item["command"] == "ls -la"  # First event added


def test_get_bash_events_with_filter(test_client):
    """Test getting bash events with command filter."""
    client, service = test_client

    # Add some test events
    action1 = ExecuteBashAction(command="echo hello")
    action2 = ExecuteBashAction(command="ls -la")

    event1 = BashEvent(action=action1)
    event2 = BashEvent(action=action2)

    service._events = [event1, event2]

    response = client.get("/api/workspace/bash-events/search?command_filter=echo")

    assert response.status_code == 200
    result = response.json()

    assert len(result["items"]) == 1  # Only the matching action
    assert result["items"][0]["command"] == "echo hello"


def test_get_bash_events_with_pagination(test_client):
    """Test bash events pagination."""
    client, service = test_client

    # Add multiple test events
    events = []
    for i in range(5):
        action = ExecuteBashAction(command=f"echo {i}")
        event = BashEvent(action=action)
        events.append(event)

    service._events = events

    # Test first page
    response = client.get("/api/workspace/bash-events/search?limit=2&offset=0")
    assert response.status_code == 200
    result = response.json()

    assert len(result["items"]) == 2
    assert result["next_page_id"] == "2"  # Next offset

    # Test second page
    response = client.get("/api/workspace/bash-events/search?limit=2&page_id=2")
    assert response.status_code == 200
    result = response.json()

    assert len(result["items"]) == 2
    assert result["next_page_id"] == "4"  # Next offset (2 + 2)


def test_get_bash_event_by_id(test_client):
    """Test getting a specific bash event by ID."""
    client, service = test_client

    action = ExecuteBashAction(command="echo test")
    event = BashEvent(action=action)

    service._events = [event]

    response = client.get(f"/api/workspace/bash-events/{event.id}")

    assert response.status_code == 200
    result = response.json()

    assert result["id"] == event.id
    assert result["action"]["command"] == "echo test"


def test_get_nonexistent_bash_event(test_client):
    """Test getting a bash event that doesn't exist."""
    client, service = test_client

    response = client.get("/api/workspace/bash-events/nonexistent-id")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_websocket_bash_events(test_client):
    """Test WebSocket bash events subscription endpoint exists."""
    client, service = test_client

    # Check if the WebSocket endpoint is registered by inspecting the app routes
    app = client.app
    websocket_routes = [
        route
        for route in app.routes
        if hasattr(route, "path") and "bash-events/socket" in route.path
    ]

    # Verify that the WebSocket route exists
    assert len(websocket_routes) > 0, "WebSocket route for bash-events/socket not found"

    # Verify it's a WebSocket route
    websocket_route = websocket_routes[0]
    assert hasattr(websocket_route, "endpoint"), "Route should have an endpoint"


def test_upload_file_error_handling(test_client):
    """Test file upload error handling."""
    client, service = test_client

    # Test with invalid file path (trying to write outside workspace)
    test_content = b"Hello, World!"

    response = client.post(
        "/api/workspace/upload",
        files={"file": ("test.txt", test_content, "text/plain")},
        data={"path": "../../../etc/passwd"},
    )

    assert response.status_code == 400
    assert "outside workspace" in response.json()["detail"].lower()


def test_execute_bash_error_handling(test_client):
    """Test bash execution error handling."""
    client, service = test_client

    with patch.object(service, "execute_bash_command") as mock_execute:
        mock_execute.side_effect = Exception("Test error")

        request_data = ExecuteBashAction(command="echo test")

        response = client.post(
            "/api/workspace/execute",
            json=request_data.model_dump(),
        )

        assert response.status_code == 500
        assert "error" in response.json()["detail"].lower()
