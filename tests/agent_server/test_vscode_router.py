"""Tests for VSCode router."""

from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from openhands.agent_server.api import create_app
from openhands.agent_server.config import Config
from openhands.agent_server.vscode_router import (
    get_vscode_connection_token,
    get_vscode_status,
    get_vscode_url,
)


@pytest.fixture
def client():
    """Create a test client."""
    config = Config()
    app = create_app(config)
    return TestClient(app)


@pytest.fixture
def mock_vscode_service():
    """Mock VSCode service for testing."""
    with patch("openhands.agent_server.vscode_router.get_vscode_service") as mock:
        yield mock.return_value


@pytest.mark.asyncio
async def test_get_vscode_connection_token_success(mock_vscode_service):
    """Test getting VSCode connection token successfully."""
    mock_vscode_service.get_connection_token.return_value = "test-token"

    response = await get_vscode_connection_token()

    assert response.token == "test-token"
    mock_vscode_service.get_connection_token.assert_called_once()


@pytest.mark.asyncio
async def test_get_vscode_connection_token_none(mock_vscode_service):
    """Test getting VSCode connection token when none available."""
    mock_vscode_service.get_connection_token.return_value = None

    response = await get_vscode_connection_token()

    assert response.token is None


@pytest.mark.asyncio
async def test_get_vscode_connection_token_error(mock_vscode_service):
    """Test getting VSCode connection token with service error."""
    mock_vscode_service.get_connection_token.side_effect = Exception("Service error")

    with pytest.raises(HTTPException) as exc_info:
        await get_vscode_connection_token()

    assert exc_info.value.status_code == 500
    assert "Failed to get VSCode token" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_get_vscode_url_success(mock_vscode_service):
    """Test getting VSCode URL successfully."""
    mock_vscode_service.get_connection_token.return_value = "test-token"
    mock_vscode_service.get_vscode_url.return_value = (
        "http://localhost:8001/?tkn=test-token&folder=/workspace"
    )

    response = await get_vscode_url("http://localhost")

    assert response.token == "test-token"
    assert response.url == "http://localhost:8001/?tkn=test-token&folder=/workspace"
    mock_vscode_service.get_vscode_url.assert_called_once_with("http://localhost")


@pytest.mark.asyncio
async def test_get_vscode_url_no_token(mock_vscode_service):
    """Test getting VSCode URL when no token available."""
    mock_vscode_service.get_connection_token.return_value = None
    mock_vscode_service.get_vscode_url.return_value = None

    response = await get_vscode_url()

    assert response.token is None
    assert response.url is None


@pytest.mark.asyncio
async def test_get_vscode_url_error(mock_vscode_service):
    """Test getting VSCode URL with service error."""
    mock_vscode_service.get_connection_token.side_effect = Exception("Service error")

    with pytest.raises(HTTPException) as exc_info:
        await get_vscode_url()

    assert exc_info.value.status_code == 500
    assert "Failed to get VSCode URL" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_get_vscode_status_running(mock_vscode_service):
    """Test getting VSCode status when running."""
    mock_vscode_service.is_running.return_value = True

    response = await get_vscode_status()

    assert response == {"running": True}
    mock_vscode_service.is_running.assert_called_once()


@pytest.mark.asyncio
async def test_get_vscode_status_not_running(mock_vscode_service):
    """Test getting VSCode status when not running."""
    mock_vscode_service.is_running.return_value = False

    response = await get_vscode_status()

    assert response == {"running": False}


@pytest.mark.asyncio
async def test_get_vscode_status_error(mock_vscode_service):
    """Test getting VSCode status with service error."""
    mock_vscode_service.is_running.side_effect = Exception("Service error")

    with pytest.raises(HTTPException) as exc_info:
        await get_vscode_status()

    assert exc_info.value.status_code == 500
    assert "Failed to get VSCode status" in str(exc_info.value.detail)


def test_vscode_router_endpoints_integration(client):
    """Test VSCode router endpoints through the API."""
    # Patch both the router import and the service module
    with (
        patch(
            "openhands.agent_server.vscode_router.get_vscode_service"
        ) as mock_service_getter,
        patch("openhands.agent_server.api.get_vscode_service") as mock_api_service,
    ):
        mock_service = mock_service_getter.return_value
        mock_service.get_connection_token.return_value = "integration-token"
        mock_service.get_vscode_url.return_value = (
            "http://localhost:8001/?tkn=integration-token"
        )
        mock_service.is_running.return_value = True

        # Mock the API service to avoid startup
        mock_api_service.return_value.start.return_value = True
        mock_api_service.return_value.stop.return_value = None

        # Test connection token endpoint
        response = client.get("/api/vscode/connection_token")
        assert response.status_code == 200
        data = response.json()
        assert data["token"] == "integration-token"

        # Test URL endpoint
        response = client.get("/api/vscode/url")
        assert response.status_code == 200
        data = response.json()
        assert data["token"] == "integration-token"
        assert data["url"] == "http://localhost:8001/?tkn=integration-token"

        # Test URL endpoint with custom base URL
        response = client.get("/api/vscode/url?base_url=http://example.com")
        assert response.status_code == 200

        # Test status endpoint
        response = client.get("/api/vscode/status")
        assert response.status_code == 200
        data = response.json()
        assert data["running"] is True


def test_vscode_router_endpoints_with_errors(client):
    """Test VSCode router endpoints with service errors."""
    # Patch both the router import and the service module
    with (
        patch(
            "openhands.agent_server.vscode_router.get_vscode_service"
        ) as mock_service_getter,
        patch("openhands.agent_server.api.get_vscode_service") as mock_api_service,
    ):
        mock_service = mock_service_getter.return_value
        mock_service.get_connection_token.side_effect = Exception("Service down")
        mock_service.is_running.side_effect = Exception("Service down")

        # Mock the API service to avoid startup
        mock_api_service.return_value.start.return_value = True
        mock_api_service.return_value.stop.return_value = None

        # Test connection token endpoint error
        response = client.get("/api/vscode/connection_token")
        assert response.status_code == 500
        data = response.json()
        # API hides detailed error messages for 5xx errors for security
        assert data["detail"] == "Internal Server Error"

        # Test URL endpoint error
        response = client.get("/api/vscode/url")
        assert response.status_code == 500
        data = response.json()
        assert data["detail"] == "Internal Server Error"

        # Test status endpoint error
        response = client.get("/api/vscode/status")
        assert response.status_code == 500
        data = response.json()
        assert data["detail"] == "Internal Server Error"
