"""
Tests for WebSocket authentication using query parameters.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from openhands.agent_server.api import create_app
from openhands.agent_server.config import Config


def assert_auth_failure(exc_info):
    """Helper to check if exception indicates authentication failure."""
    exc_str = str(exc_info.value)
    exc_type = type(exc_info.value).__name__
    has_401 = (
        "401" in exc_str
        or hasattr(exc_info.value, "status_code")
        and exc_info.value.status_code == 401
    )
    has_unauthorized = "Unauthorized" in exc_str
    assert has_401 or has_unauthorized, (
        f"Expected 401/Unauthorized, got {exc_type}: {exc_str}"
    )


@pytest.fixture
def client_no_auth():
    """Create a test client without authentication."""
    config = Config(session_api_keys=[])
    return TestClient(create_app(config))


@pytest.fixture
def client_with_auth():
    """Create a test client with session API key authentication."""
    config = Config(session_api_keys=["test-key-123"])
    return TestClient(create_app(config))


@pytest.fixture
def client_with_multiple_keys():
    """Create a test client with multiple session API keys."""
    config = Config(session_api_keys=["key-1", "key-2", "key-3"])
    return TestClient(create_app(config))


@pytest.fixture
def sample_conversation_id():
    """Return a sample conversation ID."""
    return str(uuid4())


class TestEventRouterWebSocketAuth:
    """Test WebSocket authentication for event router."""

    def test_websocket_no_auth_required(self, client_no_auth, sample_conversation_id):
        """Test WebSocket connection works without auth when no keys configured."""
        url = f"/api/conversations/{sample_conversation_id}/events/socket"

        # Should be able to connect without query parameters
        with pytest.raises(Exception):
            # Connection will fail due to missing conversation, but not due to auth
            with client_no_auth.websocket_connect(url):
                pass

    def test_websocket_auth_missing_key(self, client_with_auth, sample_conversation_id):
        """Test WebSocket connection fails without session_api_key query parameter."""
        url = f"/api/conversations/{sample_conversation_id}/events/socket"

        # Should fail with 401 due to missing auth
        with pytest.raises(Exception) as exc_info:
            with client_with_auth.websocket_connect(url):
                pass

        # The exception should indicate authentication failure
        # WebSocket connections that fail auth will raise an exception during connect
        assert_auth_failure(exc_info)

    def test_websocket_auth_invalid_key(self, client_with_auth, sample_conversation_id):
        """Test WebSocket connection fails with invalid session_api_key."""
        url = (
            f"/api/conversations/{sample_conversation_id}/events/socket"
            "?session_api_key=wrong-key"
        )

        # Should fail with 401 due to invalid auth
        with pytest.raises(Exception) as exc_info:
            with client_with_auth.websocket_connect(url):
                pass

        assert_auth_failure(exc_info)

    def test_websocket_auth_valid_key(self, client_with_auth, sample_conversation_id):
        """Test WebSocket connection succeeds with valid session_api_key."""
        url = (
            f"/api/conversations/{sample_conversation_id}/events/socket"
            "?session_api_key=test-key-123"
        )

        # Should pass auth but may fail due to missing conversation
        with pytest.raises(Exception) as exc_info:
            with client_with_auth.websocket_connect(url):
                pass

        # Should not be an auth error (401), but likely a 404 for missing conversation
        assert "401" not in str(exc_info.value) and "Unauthorized" not in str(
            exc_info.value
        )

    def test_websocket_auth_multiple_keys(
        self, client_with_multiple_keys, sample_conversation_id
    ):
        """Test WebSocket connection works with any valid key from multiple keys."""
        base_url = f"/api/conversations/{sample_conversation_id}/events/socket"

        for key in ["key-1", "key-2", "key-3"]:
            url = f"{base_url}?session_api_key={key}"

            with pytest.raises(Exception) as exc_info:
                with client_with_multiple_keys.websocket_connect(url):
                    pass

            # Should not be an auth error
            assert "401" not in str(exc_info.value) and "Unauthorized" not in str(
                exc_info.value
            )

    def test_websocket_auth_case_sensitive_key(self, sample_conversation_id):
        """Test that WebSocket API key matching is case-sensitive."""
        config = Config(session_api_keys=["Test-Key-123"])
        client = TestClient(create_app(config))
        base_url = f"/api/conversations/{sample_conversation_id}/events/socket"

        # Exact match should work (pass auth, fail on missing conversation)
        url = f"{base_url}?session_api_key=Test-Key-123"
        with pytest.raises(Exception) as exc_info:
            with client.websocket_connect(url):
                pass
        assert "401" not in str(exc_info.value) and "Unauthorized" not in str(
            exc_info.value
        )

        # Case mismatch should fail auth
        url = f"{base_url}?session_api_key=test-key-123"
        with pytest.raises(Exception) as exc_info:
            with client.websocket_connect(url):
                pass
        assert_auth_failure(exc_info)


class TestBashRouterWebSocketAuth:
    """Test WebSocket authentication for bash router."""

    def test_bash_websocket_no_auth_required(self, client_no_auth):
        """Test bash WebSocket connection works without auth when no keys configured."""
        url = "/api/bash/bash_events/socket"

        # Should be able to connect without query parameters
        # Connection might succeed or fail for other reasons, but not auth
        try:
            with client_no_auth.websocket_connect(url):
                pass
        except Exception as e:
            # Should not be an auth error
            assert "401" not in str(e) and "Unauthorized" not in str(e)

    def test_bash_websocket_auth_missing_key(self, client_with_auth):
        """Test bash WebSocket connection fails without session_api_key parameter."""
        url = "/api/bash/bash_events/socket"

        # Should fail with 401 due to missing auth
        with pytest.raises(Exception) as exc_info:
            with client_with_auth.websocket_connect(url):
                pass

        assert_auth_failure(exc_info)

    def test_bash_websocket_auth_invalid_key(self, client_with_auth):
        """Test bash WebSocket connection fails with invalid session_api_key."""
        url = "/api/bash/bash_events/socket?session_api_key=wrong-key"

        # Should fail with 401 due to invalid auth
        with pytest.raises(Exception) as exc_info:
            with client_with_auth.websocket_connect(url):
                pass

        assert_auth_failure(exc_info)

    def test_bash_websocket_auth_valid_key(self, client_with_auth):
        """Test bash WebSocket connection succeeds with valid session_api_key."""
        url = "/api/bash/bash_events/socket?session_api_key=test-key-123"

        # Should pass auth and potentially establish connection
        try:
            with client_with_auth.websocket_connect(url):
                pass
        except Exception as exc_info:
            # Should not be an auth error
            assert "401" not in str(exc_info) and "Unauthorized" not in str(exc_info)

    def test_bash_websocket_auth_multiple_keys(self, client_with_multiple_keys):
        """Test bash WebSocket connection works with any valid key."""
        base_url = "/api/bash/bash_events/socket"

        for key in ["key-1", "key-2", "key-3"]:
            url = f"{base_url}?session_api_key={key}"

            try:
                with client_with_multiple_keys.websocket_connect(url):
                    pass
            except Exception as exc_info:
                # Should not be an auth error
                assert "401" not in str(exc_info) and "Unauthorized" not in str(
                    exc_info
                )


class TestWebSocketQueryParameterHandling:
    """Test query parameter handling for WebSocket authentication."""

    def test_websocket_auth_url_encoding(
        self, client_with_auth, sample_conversation_id
    ):
        """Test WebSocket auth with URL-encoded special characters in key."""
        # Create client with special character key
        config = Config(session_api_keys=["key@with#special$chars"])
        client = TestClient(create_app(config))

        # URL encode the special characters
        import urllib.parse

        encoded_key = urllib.parse.quote("key@with#special$chars")
        url = (
            f"/api/conversations/{sample_conversation_id}/events/socket"
            f"?session_api_key={encoded_key}"
        )

        with pytest.raises(Exception) as exc_info:
            with client.websocket_connect(url):
                pass

        # Should not be an auth error
        assert "401" not in str(exc_info.value) and "Unauthorized" not in str(
            exc_info.value
        )

    def test_websocket_auth_empty_key_parameter(
        self, client_with_auth, sample_conversation_id
    ):
        """Test WebSocket auth with empty session_api_key parameter."""
        url = (
            f"/api/conversations/{sample_conversation_id}/events/socket"
            "?session_api_key="
        )

        # Should fail with 401 due to empty key
        with pytest.raises(Exception) as exc_info:
            with client_with_auth.websocket_connect(url):
                pass

        assert_auth_failure(exc_info)

    def test_websocket_auth_multiple_query_params(
        self, client_with_auth, sample_conversation_id
    ):
        """Test WebSocket auth with multiple query parameters."""
        url = (
            f"/api/conversations/{sample_conversation_id}/events/socket"
            "?session_api_key=test-key-123&other_param=value"
        )

        with pytest.raises(Exception) as exc_info:
            with client_with_auth.websocket_connect(url):
                pass

        # Should not be an auth error
        assert "401" not in str(exc_info.value) and "Unauthorized" not in str(
            exc_info.value
        )


class TestBackwardCompatibility:
    """Test that HTTP endpoints still work with header-based auth."""

    def test_http_endpoints_still_use_headers(
        self, client_with_auth, sample_conversation_id
    ):
        """Test that regular HTTP endpoints still use X-Session-API-Key header."""
        # Test that HTTP endpoints work with headers
        response = client_with_auth.get(
            f"/api/conversations/{sample_conversation_id}/events/search",
            headers={"X-Session-API-Key": "test-key-123"},
        )
        assert response.status_code != 401

        # Test that HTTP endpoints fail without headers
        response = client_with_auth.get(
            f"/api/conversations/{sample_conversation_id}/events/search"
        )
        assert response.status_code == 401

        # Test that HTTP endpoints don't accept query parameters for auth
        response = client_with_auth.get(
            f"/api/conversations/{sample_conversation_id}/events/search?session_api_key=test-key-123"
        )
        assert response.status_code == 401
