"""
Unit tests for middleware functionality, specifically ValidateSessionAPIKeyMiddleware
with multiple session API keys support.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from openhands.agent_server.middleware import ValidateSessionAPIKeyMiddleware


@pytest.fixture
def app_with_middleware():
    """Create a FastAPI app with ValidateSessionAPIKeyMiddleware for testing."""
    app = FastAPI()

    @app.get("/test")
    async def test_endpoint():
        return {"message": "success"}

    @app.get("/alive")
    async def alive_endpoint():
        return {"status": "alive"}

    @app.get("/health")
    async def health_endpoint():
        return {"status": "healthy"}

    @app.get("/server_info")
    async def server_info_endpoint():
        return {"info": "server"}

    return app


def test_middleware_with_single_key(app_with_middleware):
    """Test middleware with a single session API key."""
    app_with_middleware.add_middleware(
        ValidateSessionAPIKeyMiddleware, session_api_keys=["test-key-1"]
    )

    client = TestClient(app_with_middleware, raise_server_exceptions=False)

    # Test with correct key
    response = client.get("/test", headers={"X-Session-API-Key": "test-key-1"})
    assert response.status_code == 200
    assert response.json() == {"message": "success"}

    # Test with incorrect key
    response = client.get("/test", headers={"X-Session-API-Key": "wrong-key"})
    assert response.status_code == 401

    # Test with no key
    response = client.get("/test")
    assert response.status_code == 401


def test_middleware_with_multiple_keys(app_with_middleware):
    """Test middleware with multiple session API keys."""
    app_with_middleware.add_middleware(
        ValidateSessionAPIKeyMiddleware,
        session_api_keys=["test-key-1", "test-key-2", "test-key-3"],
    )

    client = TestClient(app_with_middleware, raise_server_exceptions=False)

    # Test with first key
    response = client.get("/test", headers={"X-Session-API-Key": "test-key-1"})
    assert response.status_code == 200
    assert response.json() == {"message": "success"}

    # Test with second key
    response = client.get("/test", headers={"X-Session-API-Key": "test-key-2"})
    assert response.status_code == 200
    assert response.json() == {"message": "success"}

    # Test with third key
    response = client.get("/test", headers={"X-Session-API-Key": "test-key-3"})
    assert response.status_code == 200
    assert response.json() == {"message": "success"}

    # Test with incorrect key
    response = client.get("/test", headers={"X-Session-API-Key": "wrong-key"})
    assert response.status_code == 401

    # Test with no key
    response = client.get("/test")
    assert response.status_code == 401


def test_middleware_with_empty_keys_list(app_with_middleware):
    """Test middleware with empty session API keys list (no authentication)."""
    # When session_api_keys is empty, middleware should not be added
    # This test verifies that empty list means no authentication required
    client = TestClient(app_with_middleware, raise_server_exceptions=False)

    # Test with any key - should succeed because no middleware is added
    response = client.get("/test", headers={"X-Session-API-Key": "any-key"})
    assert response.status_code == 200

    # Test with no key - should also succeed
    response = client.get("/test")
    assert response.status_code == 200


def test_middleware_skips_health_endpoints(app_with_middleware):
    """Test that middleware skips authentication for health check endpoints."""
    app_with_middleware.add_middleware(
        ValidateSessionAPIKeyMiddleware, session_api_keys=["test-key-1"]
    )

    client = TestClient(app_with_middleware, raise_server_exceptions=False)

    # Test health endpoints without authentication
    response = client.get("/alive")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}

    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

    response = client.get("/server_info")
    assert response.status_code == 200
    assert response.json() == {"info": "server"}


def test_middleware_case_sensitivity(app_with_middleware):
    """Test that session API key matching is case-sensitive."""
    app_with_middleware.add_middleware(
        ValidateSessionAPIKeyMiddleware, session_api_keys=["Test-Key-1", "test-key-2"]
    )

    client = TestClient(app_with_middleware, raise_server_exceptions=False)

    # Test exact match
    response = client.get("/test", headers={"X-Session-API-Key": "Test-Key-1"})
    assert response.status_code == 200

    # Test case mismatch
    response = client.get("/test", headers={"X-Session-API-Key": "test-key-1"})
    assert response.status_code == 401

    # Test second key exact match
    response = client.get("/test", headers={"X-Session-API-Key": "test-key-2"})
    assert response.status_code == 200


def test_middleware_with_special_characters(app_with_middleware):
    """Test middleware with session API keys containing special characters."""
    special_keys = [
        "key-with-dashes",
        "key_with_underscores",
        "key.with.dots",
        "key@with#special$chars",
        "key with spaces",
        "key/with/slashes",
    ]

    app_with_middleware.add_middleware(
        ValidateSessionAPIKeyMiddleware, session_api_keys=special_keys
    )

    client = TestClient(app_with_middleware, raise_server_exceptions=False)

    # Test each special key
    for key in special_keys:
        response = client.get("/test", headers={"X-Session-API-Key": key})
        assert response.status_code == 200, f"Failed for key: {key}"


def test_middleware_with_duplicate_keys(app_with_middleware):
    """Test middleware behavior with duplicate keys in the list."""
    app_with_middleware.add_middleware(
        ValidateSessionAPIKeyMiddleware,
        session_api_keys=["test-key", "test-key", "other-key"],
    )

    client = TestClient(app_with_middleware, raise_server_exceptions=False)

    # Test that duplicate key still works
    response = client.get("/test", headers={"X-Session-API-Key": "test-key"})
    assert response.status_code == 200

    # Test other key
    response = client.get("/test", headers={"X-Session-API-Key": "other-key"})
    assert response.status_code == 200

    # Test invalid key
    response = client.get("/test", headers={"X-Session-API-Key": "invalid-key"})
    assert response.status_code == 401


def test_middleware_header_name_case_insensitive(app_with_middleware):
    """Test that HTTP header name matching is case-insensitive (HTTP standard)."""
    app_with_middleware.add_middleware(
        ValidateSessionAPIKeyMiddleware, session_api_keys=["test-key"]
    )

    client = TestClient(app_with_middleware, raise_server_exceptions=False)

    # Test various header name cases
    header_variations = [
        "X-Session-API-Key",
        "x-session-api-key",
        "X-SESSION-API-KEY",
        "x-Session-Api-Key",
    ]

    for header_name in header_variations:
        response = client.get("/test", headers={header_name: "test-key"})
        assert response.status_code == 200, f"Failed for header: {header_name}"
