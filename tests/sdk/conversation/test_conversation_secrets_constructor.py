"""Tests for Conversation constructor with secrets parameter."""

import tempfile
from unittest.mock import Mock, patch

import pytest
from pydantic import SecretStr

from openhands.sdk.agent import Agent
from openhands.sdk.conversation import Conversation
from openhands.sdk.conversation.impl.local_conversation import LocalConversation
from openhands.sdk.conversation.impl.remote_conversation import RemoteConversation
from openhands.sdk.llm import LLM
from openhands.sdk.workspace import RemoteWorkspace


def create_test_agent() -> Agent:
    """Create a test agent."""
    llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="test-llm")
    return Agent(llm=llm, tools=[])


def create_mock_http_responses():
    """Create mock HTTP responses for RemoteConversation."""
    # Mock the POST response for conversation creation
    mock_post_response = Mock()
    mock_post_response.raise_for_status.return_value = None
    mock_post_response.json.return_value = {
        "id": "12345678-1234-5678-9abc-123456789abc"
    }

    # Mock the GET response for events sync
    mock_get_response = Mock()
    mock_get_response.raise_for_status.return_value = None
    mock_get_response.json.return_value = {"items": []}

    return mock_post_response, mock_get_response


def test_local_conversation_constructor_with_secrets():
    """Test LocalConversation constructor accepts and initializes secrets."""
    agent = create_test_agent()

    # Test secrets as dict[str, str]
    test_secrets = {
        "API_KEY": "test-api-key-123",
        "DATABASE_URL": "postgresql://localhost/test",
        "AUTH_TOKEN": "bearer-token-456",
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        conv = Conversation(
            agent=agent, workspace=tmpdir, persistence_dir=tmpdir, secrets=test_secrets
        )

        # Verify it's a LocalConversation
        assert isinstance(conv, LocalConversation)

        # Verify secrets were initialized
        secrets_manager = conv.state.secrets_manager
        assert secrets_manager is not None

        # Verify secrets are accessible through the secrets manager
        env_vars = secrets_manager.get_secrets_as_env_vars("echo $API_KEY")
        assert env_vars == {"API_KEY": "test-api-key-123"}

        env_vars = secrets_manager.get_secrets_as_env_vars("echo $DATABASE_URL")
        assert env_vars == {"DATABASE_URL": "postgresql://localhost/test"}

        # Test multiple secrets in one command
        env_vars = secrets_manager.get_secrets_as_env_vars(
            "export API_KEY=$API_KEY && export AUTH_TOKEN=$AUTH_TOKEN"
        )
        assert env_vars == {
            "API_KEY": "test-api-key-123",
            "AUTH_TOKEN": "bearer-token-456",
        }


def test_local_conversation_constructor_with_callable_secrets():
    """Test LocalConversation constructor with callable secrets."""
    agent = create_test_agent()

    def get_dynamic_token():
        return "dynamic-token-789"

    def get_api_key():
        return "callable-api-key"

    test_secrets = {
        "STATIC_KEY": "static-value",
        "DYNAMIC_TOKEN": get_dynamic_token,
        "API_KEY": get_api_key,
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        conv = Conversation(
            agent=agent, workspace=tmpdir, persistence_dir=tmpdir, secrets=test_secrets
        )

        # Verify it's a LocalConversation
        assert isinstance(conv, LocalConversation)

        # Verify callable secrets work
        secrets_manager = conv.state.secrets_manager

        env_vars = secrets_manager.get_secrets_as_env_vars("echo $DYNAMIC_TOKEN")
        assert env_vars == {"DYNAMIC_TOKEN": "dynamic-token-789"}

        env_vars = secrets_manager.get_secrets_as_env_vars("echo $API_KEY")
        assert env_vars == {"API_KEY": "callable-api-key"}

        env_vars = secrets_manager.get_secrets_as_env_vars("echo $STATIC_KEY")
        assert env_vars == {"STATIC_KEY": "static-value"}


def test_local_conversation_constructor_without_secrets():
    """Test LocalConversation constructor works without secrets parameter."""
    agent = create_test_agent()

    with tempfile.TemporaryDirectory() as tmpdir:
        conv = Conversation(
            agent=agent,
            workspace=tmpdir,
            persistence_dir=tmpdir,
            # No secrets parameter
        )

        # Verify it's a LocalConversation
        assert isinstance(conv, LocalConversation)

        # Verify secrets manager exists but is empty
        secrets_manager = conv.state.secrets_manager
        assert secrets_manager is not None

        # Should return empty dict for any command
        env_vars = secrets_manager.get_secrets_as_env_vars("echo $API_KEY")
        assert env_vars == {}


def test_local_conversation_constructor_with_empty_secrets():
    """Test LocalConversation constructor with empty secrets dict."""
    agent = create_test_agent()

    with tempfile.TemporaryDirectory() as tmpdir:
        conv = Conversation(
            agent=agent,
            workspace=tmpdir,
            persistence_dir=tmpdir,
            secrets={},  # Empty dict
        )

        # Verify it's a LocalConversation
        assert isinstance(conv, LocalConversation)

        # Verify secrets manager exists but is empty
        secrets_manager = conv.state.secrets_manager
        assert secrets_manager is not None

        # Should return empty dict for any command
        env_vars = secrets_manager.get_secrets_as_env_vars("echo $API_KEY")
        assert env_vars == {}


@pytest.mark.parametrize("api_key", [None, "test-api-key"])
@patch("httpx.Client")
def test_remote_conversation_constructor_with_secrets(mock_httpx_client, api_key):
    """Test RemoteConversation constructor accepts and initializes secrets."""
    agent = create_test_agent()

    # Mock httpx client and its responses
    mock_client_instance = Mock()
    mock_httpx_client.return_value = mock_client_instance

    mock_post_response, mock_get_response = create_mock_http_responses()
    mock_client_instance.post.return_value = mock_post_response
    mock_client_instance.get.return_value = mock_get_response

    test_secrets = {
        "API_KEY": "test-api-key-123",
        "DATABASE_URL": "postgresql://localhost/test",
    }

    with patch(
        "openhands.sdk.conversation.impl.remote_conversation.WebSocketCallbackClient"
    ):
        # Create a RemoteWorkspace
        workspace = RemoteWorkspace(
            host="http://localhost:3000",
            api_key=api_key,
            working_dir="/workspace/project",
        )

        conv = Conversation(agent=agent, workspace=workspace, secrets=test_secrets)

        # Verify it's a RemoteConversation
        assert isinstance(conv, RemoteConversation)

        # Verify that update_secrets was called during initialization
        # The RemoteConversation should have made a POST request to update secrets
        mock_client_instance.post.assert_any_call(
            "/api/conversations/12345678-1234-5678-9abc-123456789abc/secrets",
            json={"secrets": test_secrets},
        )


@patch("httpx.Client")
def test_remote_conversation_constructor_with_callable_secrets(mock_httpx_client):
    """Test RemoteConversation constructor with callable secrets."""
    agent = create_test_agent()

    # Mock httpx client and its responses
    mock_client_instance = Mock()
    mock_httpx_client.return_value = mock_client_instance

    mock_post_response, mock_get_response = create_mock_http_responses()
    mock_client_instance.post.return_value = mock_post_response
    mock_client_instance.get.return_value = mock_get_response

    def get_dynamic_token():
        return "dynamic-token-789"

    test_secrets = {"STATIC_KEY": "static-value", "DYNAMIC_TOKEN": get_dynamic_token}

    with patch(
        "openhands.sdk.conversation.impl.remote_conversation.WebSocketCallbackClient"
    ):
        # Create a RemoteWorkspace
        workspace = RemoteWorkspace(
            host="http://localhost:3000",
            api_key="test-api-key",
            working_dir="/workspace/project",
        )

        conv = Conversation(agent=agent, workspace=workspace, secrets=test_secrets)

        # Verify it's a RemoteConversation
        assert isinstance(conv, RemoteConversation)

        # Verify that callable secrets were resolved and sent to server
        expected_serialized_secrets = {
            "STATIC_KEY": "static-value",
            "DYNAMIC_TOKEN": "dynamic-token-789",  # Callable was invoked
        }

        mock_client_instance.post.assert_any_call(
            "/api/conversations/12345678-1234-5678-9abc-123456789abc/secrets",
            json={"secrets": expected_serialized_secrets},
        )


@patch("httpx.Client")
def test_remote_conversation_constructor_without_secrets(mock_httpx_client):
    """Test RemoteConversation constructor works without secrets parameter."""
    agent = create_test_agent()

    # Mock httpx client and its responses
    mock_client_instance = Mock()
    mock_httpx_client.return_value = mock_client_instance

    mock_post_response, mock_get_response = create_mock_http_responses()
    mock_client_instance.post.return_value = mock_post_response
    mock_client_instance.get.return_value = mock_get_response

    with patch(
        "openhands.sdk.conversation.impl.remote_conversation.WebSocketCallbackClient"
    ):
        # Create a RemoteWorkspace
        workspace = RemoteWorkspace(
            host="http://localhost:3000",
            api_key="test-api-key",
            working_dir="/workspace/project",
        )

        conv = Conversation(
            agent=agent,
            workspace=workspace,
            # No secrets parameter
        )

        # Verify it's a RemoteConversation
        assert isinstance(conv, RemoteConversation)

        # Verify that no secrets update call was made
        secrets_calls = [
            call
            for call in mock_client_instance.post.call_args_list
            if "/secrets" in str(call)
        ]
        assert len(secrets_calls) == 0


@patch("httpx.Client")
def test_conversation_factory_routing_with_secrets(mock_httpx_client):
    """Test that Conversation factory correctly routes to Local/Remote with secrets."""
    agent = create_test_agent()
    test_secrets = {"API_KEY": "test-key"}

    # Test LocalConversation routing
    with tempfile.TemporaryDirectory() as tmpdir:
        local_conv = Conversation(agent=agent, workspace=tmpdir, secrets=test_secrets)
        assert isinstance(local_conv, LocalConversation)

    # Test RemoteConversation routing
    # Mock httpx client and its responses
    mock_client_instance = Mock()
    mock_httpx_client.return_value = mock_client_instance

    mock_post_response, mock_get_response = create_mock_http_responses()
    mock_client_instance.post.return_value = mock_post_response
    mock_client_instance.get.return_value = mock_get_response

    with patch(
        "openhands.sdk.conversation.impl.remote_conversation.WebSocketCallbackClient"
    ):
        workspace = RemoteWorkspace(
            host="http://localhost:3000",
            api_key="test-api-key",
            working_dir="/workspace/project",
        )

        remote_conv = Conversation(
            agent=agent, workspace=workspace, secrets=test_secrets
        )
        assert isinstance(remote_conv, RemoteConversation)


def test_secrets_parameter_type_validation():
    """Test that secrets parameter accepts correct types."""
    agent = create_test_agent()

    # Test with valid dict[str, str]
    with tempfile.TemporaryDirectory() as tmpdir:
        conv = Conversation(agent=agent, workspace=tmpdir, secrets={"KEY": "value"})
        assert isinstance(conv, LocalConversation)

    # Test with callable values
    def get_secret():
        return "secret-value"

    with tempfile.TemporaryDirectory() as tmpdir:
        conv = Conversation(agent=agent, workspace=tmpdir, secrets={"KEY": get_secret})  # type: ignore[dict-item]
        assert isinstance(conv, LocalConversation)

    # Test with None (should work)
    with tempfile.TemporaryDirectory() as tmpdir:
        conv = Conversation(agent=agent, workspace=tmpdir, secrets=None)
        assert isinstance(conv, LocalConversation)
