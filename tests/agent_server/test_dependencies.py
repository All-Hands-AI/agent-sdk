"""
Unit tests for dependency-based authentication functionality.
Tests the check_session_api_key dependency with multiple session API keys support.
"""

from unittest.mock import patch

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from openhands.agent_server.config import Config
from openhands.agent_server.dependencies import (
    _SESSION_API_KEY_HEADER,
    check_session_api_key,
    create_session_api_key_dependency,
)


@pytest.fixture
def app_with_dependency():
    """Create a FastAPI app with check_session_api_key dependency for testing."""
    app = FastAPI()

    @app.get("/test")
    async def test_endpoint():
        return {"message": "success"}

    @app.get("/api/test", dependencies=[Depends(check_session_api_key)])
    async def api_test_endpoint():
        return {"message": "success"}

    @app.get("/api/protected", dependencies=[Depends(check_session_api_key)])
    async def protected_endpoint():
        return {"message": "protected"}

    @app.get("/public")
    async def public_endpoint():
        return {"message": "public"}

    return app


def test_dependency_no_auth_required():
    """Test that when no session API keys are configured, no authentication is required."""  # noqa: E501
    with patch("openhands.agent_server.dependencies.get_default_config") as mock_config:
        mock_config.return_value = Config(session_api_keys=[])

        app = FastAPI()

        @app.get("/test", dependencies=[Depends(check_session_api_key)])
        async def test_endpoint():
            return {"message": "success"}

        client = TestClient(app)

        # Should work without any headers
        response = client.get("/test")
        assert response.status_code == 200
        assert response.json() == {"message": "success"}


def test_dependency_single_key_valid():
    """Test authentication with a single valid session API key."""
    with patch("openhands.agent_server.dependencies.get_default_config") as mock_config:
        mock_config.return_value = Config(session_api_keys=["test-key-123"])

        app = FastAPI()

        @app.get("/test", dependencies=[Depends(check_session_api_key)])
        async def test_endpoint():
            return {"message": "success"}

        client = TestClient(app)

        # Should work with valid key
        response = client.get("/test", headers={"X-Session-API-Key": "test-key-123"})
        assert response.status_code == 200
        assert response.json() == {"message": "success"}


def test_dependency_single_key_invalid():
    """Test authentication with an invalid session API key."""
    with patch("openhands.agent_server.dependencies.get_default_config") as mock_config:
        mock_config.return_value = Config(session_api_keys=["test-key-123"])

        app = FastAPI()

        @app.get("/test", dependencies=[Depends(check_session_api_key)])
        async def test_endpoint():
            return {"message": "success"}

        client = TestClient(app, raise_server_exceptions=False)

        # Should fail with invalid key
        response = client.get("/test", headers={"X-Session-API-Key": "wrong-key"})
        assert response.status_code == 401


def test_dependency_single_key_missing():
    """Test authentication when session API key header is missing."""
    with patch("openhands.agent_server.dependencies.get_default_config") as mock_config:
        mock_config.return_value = Config(session_api_keys=["test-key-123"])

        app = FastAPI()

        @app.get("/test", dependencies=[Depends(check_session_api_key)])
        async def test_endpoint():
            return {"message": "success"}

        client = TestClient(app, raise_server_exceptions=False)

        # Should fail without header
        response = client.get("/test")
        assert response.status_code == 401


def test_dependency_multiple_keys_valid():
    """Test authentication with multiple valid session API keys."""
    with patch("openhands.agent_server.dependencies.get_default_config") as mock_config:
        mock_config.return_value = Config(session_api_keys=["key-1", "key-2", "key-3"])

        app = FastAPI()

        @app.get("/test", dependencies=[Depends(check_session_api_key)])
        async def test_endpoint():
            return {"message": "success"}

        client = TestClient(app)

        # Test each valid key
        for key in ["key-1", "key-2", "key-3"]:
            response = client.get("/test", headers={"X-Session-API-Key": key})
            assert response.status_code == 200
            assert response.json() == {"message": "success"}


def test_dependency_multiple_keys_invalid():
    """Test authentication with invalid key when multiple keys are configured."""
    with patch("openhands.agent_server.dependencies.get_default_config") as mock_config:
        mock_config.return_value = Config(session_api_keys=["key-1", "key-2", "key-3"])

        app = FastAPI()

        @app.get("/test", dependencies=[Depends(check_session_api_key)])
        async def test_endpoint():
            return {"message": "success"}

        client = TestClient(app, raise_server_exceptions=False)

        # Should fail with invalid key
        response = client.get("/test", headers={"X-Session-API-Key": "invalid-key"})
        assert response.status_code == 401


def test_dependency_case_sensitivity():
    """Test that session API key matching is case-sensitive."""
    with patch("openhands.agent_server.dependencies.get_default_config") as mock_config:
        mock_config.return_value = Config(session_api_keys=["Test-Key-1", "test-key-2"])

        app = FastAPI()

        @app.get("/test", dependencies=[Depends(check_session_api_key)])
        async def test_endpoint():
            return {"message": "success"}

        client = TestClient(app, raise_server_exceptions=False)

        # Test exact match
        response = client.get("/test", headers={"X-Session-API-Key": "Test-Key-1"})
        assert response.status_code == 200

        # Test case mismatch
        response = client.get("/test", headers={"X-Session-API-Key": "test-key-1"})
        assert response.status_code == 401

        # Test second key exact match
        response = client.get("/test", headers={"X-Session-API-Key": "test-key-2"})
        assert response.status_code == 200


def test_dependency_special_characters():
    """Test dependency with session API keys containing special characters."""
    special_keys = [
        "key-with-dashes",
        "key_with_underscores",
        "key.with.dots",
        "key@with#special$chars",
        "key with spaces",
        "key/with/slashes",
    ]

    with patch("openhands.agent_server.dependencies.get_default_config") as mock_config:
        mock_config.return_value = Config(session_api_keys=special_keys)

        app = FastAPI()

        @app.get("/test", dependencies=[Depends(check_session_api_key)])
        async def test_endpoint():
            return {"message": "success"}

        client = TestClient(app)

        # Test each special key
        for key in special_keys:
            response = client.get("/test", headers={"X-Session-API-Key": key})
            assert response.status_code == 200, f"Failed for key: {key}"


def test_dependency_duplicate_keys():
    """Test dependency behavior with duplicate keys in the list."""
    with patch("openhands.agent_server.dependencies.get_default_config") as mock_config:
        mock_config.return_value = Config(
            session_api_keys=["test-key", "test-key", "other-key"]
        )

        app = FastAPI()

        @app.get("/test", dependencies=[Depends(check_session_api_key)])
        async def test_endpoint():
            return {"message": "success"}

        client = TestClient(app, raise_server_exceptions=False)

        # Test that duplicate key still works
        response = client.get("/test", headers={"X-Session-API-Key": "test-key"})
        assert response.status_code == 200

        # Test other key
        response = client.get("/test", headers={"X-Session-API-Key": "other-key"})
        assert response.status_code == 200

        # Test invalid key
        response = client.get("/test", headers={"X-Session-API-Key": "invalid-key"})
        assert response.status_code == 401


def test_dependency_header_name_case_insensitive():
    """Test that HTTP header name matching is case-insensitive (HTTP standard)."""
    with patch("openhands.agent_server.dependencies.get_default_config") as mock_config:
        mock_config.return_value = Config(session_api_keys=["test-key"])

        app = FastAPI()

        @app.get("/test", dependencies=[Depends(check_session_api_key)])
        async def test_endpoint():
            return {"message": "success"}

        client = TestClient(app)

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


def test_dependency_mixed_protected_unprotected_endpoints():
    """Test that dependency only affects endpoints that use it."""
    with patch("openhands.agent_server.dependencies.get_default_config") as mock_config:
        mock_config.return_value = Config(session_api_keys=["test-key"])

        app = FastAPI()

        @app.get("/protected", dependencies=[Depends(check_session_api_key)])
        async def protected_endpoint():
            return {"message": "protected"}

        @app.get("/public")
        async def public_endpoint():
            return {"message": "public"}

        client = TestClient(app, raise_server_exceptions=False)

        # Public endpoint should work without auth
        response = client.get("/public")
        assert response.status_code == 200
        assert response.json() == {"message": "public"}

        # Protected endpoint should fail without auth
        response = client.get("/protected")
        assert response.status_code == 401

        # Protected endpoint should work with valid auth
        response = client.get("/protected", headers={"X-Session-API-Key": "test-key"})
        assert response.status_code == 200
        assert response.json() == {"message": "protected"}


def test_api_key_header_configuration():
    """Test that the APIKeyHeader is configured correctly."""
    assert _SESSION_API_KEY_HEADER.model.name == "X-Session-API-Key"
    assert _SESSION_API_KEY_HEADER.auto_error is False


def test_dependency_function_direct_call():
    """Test calling the dependency function directly."""
    with patch("openhands.agent_server.dependencies.get_default_config") as mock_config:
        # Test with no keys configured
        mock_config.return_value = Config(session_api_keys=[])
        check_session_api_key(None)  # Should not raise
        check_session_api_key("any-key")  # Should not raise

        # Test with keys configured
        mock_config.return_value = Config(session_api_keys=["valid-key"])
        check_session_api_key("valid-key")  # Should not raise

        # Test with invalid key
        with pytest.raises(HTTPException) as exc_info:
            check_session_api_key("invalid-key")
        assert exc_info.value.status_code == 401

        # Test with None when keys are required
        with pytest.raises(HTTPException) as exc_info:
            check_session_api_key(None)
        assert exc_info.value.status_code == 401


def test_dependency_integration_with_real_config():
    """Integration test using actual config loading (not mocked)."""
    from openhands.agent_server.config import get_default_config

    # This test uses the actual config, so it should work with empty keys
    original_config = get_default_config()

    app = FastAPI()

    @app.get("/test", dependencies=[Depends(check_session_api_key)])
    async def test_endpoint():
        return {"message": "success"}

    client = TestClient(app)

    # If no session keys are configured in the actual config, this should work
    if not original_config.session_api_keys:
        response = client.get("/test")
        assert response.status_code == 200
    else:
        # If keys are configured, we'd need a valid key
        # This is more of a documentation of expected behavior
        pass


def test_create_session_api_key_dependency():
    """Test the dependency factory function."""
    config = Config(session_api_keys=["factory-key"])
    dependency_func = create_session_api_key_dependency(config)

    # Test with valid key
    dependency_func("factory-key")  # Should not raise

    # Test with invalid key
    with pytest.raises(HTTPException) as exc_info:
        dependency_func("invalid-key")
    assert exc_info.value.status_code == 401

    # Test with None when keys are required
    with pytest.raises(HTTPException) as exc_info:
        dependency_func(None)
    assert exc_info.value.status_code == 401


def test_create_session_api_key_dependency_no_keys():
    """Test the dependency factory with no keys configured."""
    config = Config(session_api_keys=[])
    dependency_func = create_session_api_key_dependency(config)

    # Should work with any key or None when no keys are configured
    dependency_func("any-key")  # Should not raise
    dependency_func(None)  # Should not raise


def test_create_session_api_key_dependency_in_fastapi():
    """Test the dependency factory integrated with FastAPI."""
    config = Config(session_api_keys=["factory-test-key"])
    dependency_func = create_session_api_key_dependency(config)

    app = FastAPI()

    @app.get("/test", dependencies=[Depends(dependency_func)])
    async def test_endpoint():
        return {"message": "success"}

    client = TestClient(app, raise_server_exceptions=False)

    # Test without auth
    response = client.get("/test")
    assert response.status_code == 401

    # Test with valid auth
    response = client.get("/test", headers={"X-Session-API-Key": "factory-test-key"})
    assert response.status_code == 200

    # Test with invalid auth
    response = client.get("/test", headers={"X-Session-API-Key": "wrong-key"})
    assert response.status_code == 401
