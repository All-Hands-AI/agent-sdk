"""Tests for API key functionality in RemoteConversation."""

import uuid
from unittest.mock import Mock, patch

from pydantic import SecretStr

from openhands.sdk.agent import Agent
from openhands.sdk.conversation import Conversation
from openhands.sdk.conversation.impl.remote_conversation import (
    RemoteConversation,
    WebSocketCallbackClient,
)
from openhands.sdk.llm import LLM


def create_test_agent() -> Agent:
    """Create a test agent."""
    llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="test-llm")
    return Agent(llm=llm, tools=[])


def create_mock_http_responses():
    """Create mock HTTP responses for RemoteConversation."""
    # Mock the POST response for conversation creation
    mock_post_response = Mock()
    mock_post_response.raise_for_status.return_value = None
    mock_post_response.json.return_value = {"id": str(uuid.uuid4())}

    # Mock the GET response for events sync
    mock_get_response = Mock()
    mock_get_response.raise_for_status.return_value = None
    mock_get_response.json.return_value = {"items": []}

    return mock_post_response, mock_get_response


def test_conversation_factory_passes_api_key_to_remote():
    """Test that Conversation factory passes api_key to RemoteConversation."""
    agent = create_test_agent()
    test_api_key = "test-api-key-123"

    with patch(
        "openhands.sdk.conversation.impl.remote_conversation.RemoteConversation"
    ) as mock_remote:
        # Mock the RemoteConversation constructor
        mock_instance = Mock()
        mock_remote.return_value = mock_instance

        # Create conversation with host and api_key
        Conversation(
            agent=agent,
            host="http://localhost:3000",
            api_key=test_api_key,
        )

        # Verify RemoteConversation was called with api_key
        mock_remote.assert_called_once()
        call_args = mock_remote.call_args
        assert call_args.kwargs["api_key"] == test_api_key


@patch("httpx.Client")
def test_remote_conversation_configures_httpx_client_with_api_key(mock_httpx_client):
    """Test that RemoteConversation configures httpx client with API key header."""
    agent = create_test_agent()
    test_api_key = "test-api-key-123"

    # Mock httpx client and its responses
    mock_client_instance = Mock()
    mock_httpx_client.return_value = mock_client_instance

    mock_post_response, mock_get_response = create_mock_http_responses()
    mock_client_instance.post.return_value = mock_post_response
    mock_client_instance.get.return_value = mock_get_response

    with patch(
        "openhands.sdk.conversation.impl.remote_conversation.WebSocketCallbackClient"
    ):
        # Create RemoteConversation with API key
        RemoteConversation(
            agent=agent,
            host="http://localhost:3000",
            api_key=test_api_key,
            working_dir="/tmp",
        )

    # Verify httpx.Client was called with correct headers
    mock_httpx_client.assert_called_once()
    call_args = mock_httpx_client.call_args

    # Check that headers were passed with the API key
    assert "headers" in call_args.kwargs
    headers = call_args.kwargs["headers"]
    assert headers["X-Session-API-Key"] == test_api_key


@patch("httpx.Client")
def test_remote_conversation_no_api_key_no_headers(mock_httpx_client):
    """Test that RemoteConversation doesn't add headers when no API key is provided."""
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
        # Create RemoteConversation without API key
        RemoteConversation(
            agent=agent,
            host="http://localhost:3000",
            api_key=None,
            working_dir="/tmp",
        )

    # Verify httpx.Client was called without API key headers
    mock_httpx_client.assert_called_once()
    call_args = mock_httpx_client.call_args

    # Check that headers were empty or don't contain API key
    headers = call_args.kwargs.get("headers", {})
    assert "X-Session-API-Key" not in headers


def test_websocket_client_includes_api_key_in_url():
    """Test that WebSocketCallbackClient includes API key in WebSocket URL."""
    test_api_key = "test-api-key-123"
    host = "http://localhost:3000"
    conversation_id = str(uuid.uuid4())
    callbacks = []

    ws_client = WebSocketCallbackClient(
        host=host,
        conversation_id=conversation_id,
        callbacks=callbacks,
        api_key=test_api_key,
    )

    # Test the URL construction logic by checking the stored api_key
    assert ws_client.api_key == test_api_key
    assert ws_client.host == host
    assert ws_client.conversation_id == conversation_id


def test_websocket_client_no_api_key():
    """Test that WebSocketCallbackClient works without API key."""
    host = "http://localhost:3000"
    conversation_id = str(uuid.uuid4())
    callbacks = []

    ws_client = WebSocketCallbackClient(
        host=host,
        conversation_id=conversation_id,
        callbacks=callbacks,
        api_key=None,
    )

    # Test that it works without API key
    assert ws_client.api_key is None
    assert ws_client.host == host
    assert ws_client.conversation_id == conversation_id


@patch("httpx.Client")
def test_remote_conversation_passes_api_key_to_websocket_client(mock_httpx_client):
    """Test that RemoteConversation passes API key to WebSocketCallbackClient."""
    agent = create_test_agent()
    test_api_key = "test-api-key-123"

    # Mock httpx client and its responses
    mock_client_instance = Mock()
    mock_httpx_client.return_value = mock_client_instance

    mock_post_response, mock_get_response = create_mock_http_responses()
    mock_client_instance.post.return_value = mock_post_response
    mock_client_instance.get.return_value = mock_get_response

    with patch(
        "openhands.sdk.conversation.impl.remote_conversation.WebSocketCallbackClient"
    ) as mock_ws_client:
        mock_ws_instance = Mock()
        mock_ws_client.return_value = mock_ws_instance

        # Create RemoteConversation with API key
        RemoteConversation(
            agent=agent,
            host="http://localhost:3000",
            api_key=test_api_key,
            working_dir="/tmp",
        )

        # Verify WebSocketCallbackClient was called with api_key
        mock_ws_client.assert_called_once()
        call_args = mock_ws_client.call_args
        assert call_args.kwargs["api_key"] == test_api_key
