"""Test exception handling in the agent server API."""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from openhands.agent_server.api import _find_http_exception, create_app
from openhands.agent_server.config import Config


@pytest.fixture
def client():
    """Create a test client for the API."""
    return TestClient(create_app())


@pytest.fixture
def client_with_auth():
    """Create a test client with session API key authentication."""
    config = Config(session_api_key="test-key-123")
    app = create_app(config)
    return TestClient(app)


def test_find_http_exception():
    """Test the helper function for finding HTTPExceptions in ExceptionGroups."""
    # Test with single HTTPException
    http_exc = HTTPException(status_code=401, detail="Unauthorized")
    exc_group = BaseExceptionGroup("test", [http_exc])

    found = _find_http_exception(exc_group)
    assert found is http_exc

    # Test with multiple exceptions, HTTPException first
    other_exc = ValueError("Some error")
    exc_group = BaseExceptionGroup("test", [http_exc, other_exc])

    found = _find_http_exception(exc_group)
    assert found is http_exc

    # Test with no HTTPException
    exc_group = BaseExceptionGroup("test", [other_exc])

    found = _find_http_exception(exc_group)
    assert found is None

    # Test with nested ExceptionGroup
    nested_group = BaseExceptionGroup("nested", [http_exc])
    outer_group = BaseExceptionGroup("outer", [other_exc, nested_group])

    found = _find_http_exception(outer_group)
    assert found is http_exc


def test_middleware_auth_missing_key(client_with_auth):
    """Integration test: missing X-Session-API-Key should return 401."""
    # TestClient re-raises middleware exceptions, so we need to catch them
    try:
        response = client_with_auth.get(
            "/api/conversations"
        )  # This endpoint requires auth
        # If no exception, check the response
        assert response.status_code == 401
        assert (
            response.json()["detail"]
            == "Unauthorized: Invalid or missing X-Session-API-Key header"
        )
    except HTTPException as e:
        # If exception is raised, verify it's the expected 401
        assert e.status_code == 401
        assert e.detail == "Unauthorized: Invalid or missing X-Session-API-Key header"


def test_middleware_auth_invalid_key(client_with_auth):
    """Integration test: invalid X-Session-API-Key should return 401."""
    # TestClient re-raises middleware exceptions, so we need to catch them
    try:
        response = client_with_auth.get(
            "/api/conversations", headers={"X-Session-API-Key": "wrong-key"}
        )
        # If no exception, check the response
        assert response.status_code == 401
        assert (
            response.json()["detail"]
            == "Unauthorized: Invalid or missing X-Session-API-Key header"
        )
    except HTTPException as e:
        # If exception is raised, verify it's the expected 401
        assert e.status_code == 401
        assert e.detail == "Unauthorized: Invalid or missing X-Session-API-Key header"


def test_middleware_auth_valid_key(client_with_auth):
    """Integration test: valid X-Session-API-Key should allow access."""
    response = client_with_auth.get(
        "/api/conversations", headers={"X-Session-API-Key": "test-key-123"}
    )

    # Should not be 401 (might be 200 or other depending on endpoint implementation)
    assert response.status_code != 401


def test_middleware_options_request_bypasses_auth(client_with_auth):
    """Integration test: OPTIONS requests should bypass authentication for CORS."""
    response = client_with_auth.options("/api/conversations")

    # OPTIONS should not require authentication
    assert response.status_code != 401


def test_middleware_unauthenticated_paths(client_with_auth):
    """Integration test: certain paths should not require authentication."""
    # Test health check endpoints
    for path in ["/alive", "/health", "/server_info"]:
        response = client_with_auth.get(path)
        # These should not return 401 (might return 404 if endpoint doesn't exist)
        assert response.status_code != 401
