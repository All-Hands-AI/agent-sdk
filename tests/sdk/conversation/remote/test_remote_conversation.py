"""Tests for RemoteConversation."""

import uuid
from unittest.mock import Mock, patch

import httpx
import pytest
from pydantic import SecretStr

from openhands.sdk.agent import Agent
from openhands.sdk.conversation.impl.remote_conversation import RemoteConversation
from openhands.sdk.conversation.secrets_manager import SecretValue
from openhands.sdk.llm import LLM, Message, TextContent
from openhands.sdk.security.confirmation_policy import AlwaysConfirm
from openhands.sdk.workspace import RemoteWorkspace


class TestRemoteConversation:
    """Test RemoteConversation functionality."""

    def setup_method(self):
        """Set up test environment."""
        self.host = "http://localhost:8000"
        self.llm = LLM(model="gpt-4", api_key=SecretStr("test-key"))
        self.agent = Agent(llm=self.llm, tools=[])
        self.mock_client = Mock(spec=httpx.Client)
        self.workspace = RemoteWorkspace(host=self.host, working_dir="/tmp")

    def setup_mock_client(self):
        """Set up mock client for the workspace."""
        mock_client_instance = Mock()
        self.workspace._client = mock_client_instance
        return mock_client_instance

    def create_mock_conversation_response(self, conversation_id: str | None = None):
        """Create mock conversation creation response."""
        if conversation_id is None:
            conversation_id = str(uuid.uuid4())

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "id": conversation_id,
            "conversation_id": conversation_id,
        }
        return mock_response

    def create_mock_events_response(self, events: list | None = None):
        """Create mock events API response."""
        if events is None:
            events = []

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "items": events,
            "next_page_id": None,
        }
        return mock_response

    @patch(
        "openhands.sdk.conversation.impl.remote_conversation.WebSocketCallbackClient"
    )
    def test_remote_conversation_initialization_new_conversation(self, mock_ws_client):
        """Test RemoteConversation initialization with new conversation."""
        # Mock the workspace client directly
        mock_client_instance = self.setup_mock_client()

        # Mock conversation creation response
        conversation_id = str(uuid.uuid4())
        mock_conv_response = self.create_mock_conversation_response(conversation_id)

        # Mock events response
        mock_events_response = self.create_mock_events_response()

        mock_client_instance.post.return_value = mock_conv_response
        mock_client_instance.get.return_value = mock_events_response

        # Mock WebSocket client
        mock_ws_instance = Mock()
        mock_ws_client.return_value = mock_ws_instance

        # Create RemoteConversation
        conversation = RemoteConversation(
            agent=self.agent,
            workspace=self.workspace,
            max_iteration_per_run=100,
            stuck_detection=True,
        )

        # Verify conversation creation API call
        # Note: RemoteWorkspace is converted to LocalWorkspace for the server
        from openhands.sdk.workspace import LocalWorkspace

        mock_client_instance.post.assert_called_once_with(
            "/api/conversations",
            json={
                "agent": self.agent.model_dump(
                    mode="json", context={"expose_secrets": True}
                ),
                "initial_message": None,
                "max_iterations": 100,
                "stuck_detection": True,
                "workspace": LocalWorkspace(
                    working_dir=self.workspace.working_dir
                ).model_dump(),
            },
        )

        # Verify WebSocket client was created and started
        mock_ws_client.assert_called_once()
        mock_ws_instance.start.assert_called_once()

        # Verify conversation properties
        assert conversation.id == uuid.UUID(conversation_id)
        assert conversation.workspace.host == self.host
        assert conversation.max_iteration_per_run == 100

    @patch(
        "openhands.sdk.conversation.impl.remote_conversation.WebSocketCallbackClient"
    )
    def test_remote_conversation_initialization_existing_conversation(
        self, mock_ws_client
    ):
        """Test RemoteConversation initialization with existing conversation."""
        # Mock the workspace client directly
        mock_client_instance = self.setup_mock_client()

        # Mock existing conversation validation response
        conversation_id = uuid.uuid4()
        mock_validation_response = Mock()
        mock_validation_response.raise_for_status.return_value = None

        # Mock events response
        mock_events_response = self.create_mock_events_response()

        mock_client_instance.get.return_value = mock_events_response

        # Mock WebSocket client
        mock_ws_instance = Mock()
        mock_ws_client.return_value = mock_ws_instance

        # Create RemoteConversation with existing ID
        conversation = RemoteConversation(
            agent=self.agent,
            workspace=self.workspace,
            conversation_id=conversation_id,
        )

        # Verify no POST call was made (no new conversation created)
        mock_client_instance.post.assert_not_called()

        # Verify conversation ID is set correctly
        assert conversation.id == conversation_id

    @patch(
        "openhands.sdk.conversation.impl.remote_conversation.WebSocketCallbackClient"
    )
    def test_remote_conversation_send_message_string(self, mock_ws_client):
        """Test sending a string message."""
        # Setup mocks
        mock_client_instance = self.setup_mock_client()

        conversation_id = str(uuid.uuid4())
        mock_conv_response = self.create_mock_conversation_response(conversation_id)
        mock_events_response = self.create_mock_events_response()
        mock_message_response = Mock()
        mock_message_response.raise_for_status.return_value = None

        mock_client_instance.post.side_effect = [
            mock_conv_response,
            mock_message_response,
        ]
        mock_client_instance.get.return_value = mock_events_response

        mock_ws_instance = Mock()
        mock_ws_client.return_value = mock_ws_instance

        # Create conversation and send message
        conversation = RemoteConversation(agent=self.agent, workspace=self.workspace)
        conversation.send_message("Hello, world!")

        # Verify message API call was made (the exact payload structure may vary)
        # Check that a POST was made to the events endpoint
        post_calls = [
            call
            for call in mock_client_instance.post.call_args_list
            if f"/api/conversations/{conversation_id}/events" in str(call)
        ]
        assert len(post_calls) >= 1, "Should have made a POST call to events endpoint"

    @patch(
        "openhands.sdk.conversation.impl.remote_conversation.WebSocketCallbackClient"
    )
    def test_remote_conversation_send_message_object(self, mock_ws_client):
        """Test sending a Message object."""
        # Setup mocks
        mock_client_instance = self.setup_mock_client()

        conversation_id = str(uuid.uuid4())
        mock_conv_response = self.create_mock_conversation_response(conversation_id)
        mock_events_response = self.create_mock_events_response()
        mock_message_response = Mock()
        mock_message_response.raise_for_status.return_value = None

        mock_client_instance.post.side_effect = [
            mock_conv_response,
            mock_message_response,
        ]
        mock_client_instance.get.return_value = mock_events_response

        mock_ws_instance = Mock()
        mock_ws_client.return_value = mock_ws_instance

        # Create conversation and send message
        conversation = RemoteConversation(agent=self.agent, workspace=self.workspace)

        message = Message(
            role="user",
            content=[TextContent(text="Hello from message object!")],
        )
        conversation.send_message(message)

        # Verify message API call was made (the exact payload structure may vary)
        # Check that a POST was made to the events endpoint
        post_calls = [
            call
            for call in mock_client_instance.post.call_args_list
            if f"/api/conversations/{conversation_id}/events" in str(call)
        ]
        assert len(post_calls) >= 1, "Should have made a POST call to events endpoint"

    @patch(
        "openhands.sdk.conversation.impl.remote_conversation.WebSocketCallbackClient"
    )
    def test_remote_conversation_send_message_invalid_role(self, mock_ws_client):
        """Test sending a message with invalid role raises assertion error."""
        # Setup mocks
        mock_client_instance = self.setup_mock_client()

        conversation_id = str(uuid.uuid4())
        mock_conv_response = self.create_mock_conversation_response(conversation_id)
        mock_events_response = self.create_mock_events_response()

        mock_client_instance.post.return_value = mock_conv_response
        mock_client_instance.get.return_value = mock_events_response

        mock_ws_instance = Mock()
        mock_ws_client.return_value = mock_ws_instance

        # Create conversation
        conversation = RemoteConversation(agent=self.agent, workspace=self.workspace)

        # Try to send message with invalid role
        invalid_message = Message(
            role="assistant",  # Only "user" role is allowed
            content=[TextContent(text="Invalid role message")],
        )

        with pytest.raises(AssertionError, match="Only user messages are allowed"):
            conversation.send_message(invalid_message)

    @patch(
        "openhands.sdk.conversation.impl.remote_conversation.WebSocketCallbackClient"
    )
    def test_remote_conversation_run(self, mock_ws_client):
        """Test running the conversation."""
        # Setup mocks
        mock_client_instance = self.setup_mock_client()

        conversation_id = str(uuid.uuid4())
        mock_conv_response = self.create_mock_conversation_response(conversation_id)
        mock_events_response = self.create_mock_events_response()
        mock_run_response = Mock()
        mock_run_response.raise_for_status.return_value = None
        mock_run_response.status_code = 200

        mock_client_instance.post.side_effect = [mock_conv_response, mock_run_response]
        mock_client_instance.get.return_value = mock_events_response

        mock_ws_instance = Mock()
        mock_ws_client.return_value = mock_ws_instance

        # Create conversation and run
        conversation = RemoteConversation(agent=self.agent, workspace=self.workspace)
        conversation.run()

        # Verify run API call
        mock_client_instance.post.assert_any_call(
            f"/api/conversations/{conversation_id}/run",
            timeout=1800,
        )

    @patch(
        "openhands.sdk.conversation.impl.remote_conversation.WebSocketCallbackClient"
    )
    def test_remote_conversation_run_already_running(self, mock_ws_client):
        """Test running when conversation is already running (409 response)."""
        # Setup mocks
        mock_client_instance = self.setup_mock_client()

        conversation_id = str(uuid.uuid4())
        mock_conv_response = self.create_mock_conversation_response(conversation_id)
        mock_events_response = self.create_mock_events_response()
        mock_run_response = Mock()
        mock_run_response.status_code = 409  # Already running

        mock_client_instance.post.side_effect = [mock_conv_response, mock_run_response]
        mock_client_instance.get.return_value = mock_events_response

        mock_ws_instance = Mock()
        mock_ws_client.return_value = mock_ws_instance

        # Create conversation and run
        conversation = RemoteConversation(agent=self.agent, workspace=self.workspace)
        conversation.run()  # Should not raise an exception

        # Verify run API call was made
        mock_client_instance.post.assert_any_call(
            f"/api/conversations/{conversation_id}/run",
            timeout=1800,
        )

    @patch(
        "openhands.sdk.conversation.impl.remote_conversation.WebSocketCallbackClient"
    )
    def test_remote_conversation_set_confirmation_policy(self, mock_ws_client):
        """Test setting confirmation policy."""
        # Setup mocks
        mock_client_instance = self.setup_mock_client()

        conversation_id = str(uuid.uuid4())
        mock_conv_response = self.create_mock_conversation_response(conversation_id)
        mock_events_response = self.create_mock_events_response()
        mock_policy_response = Mock()
        mock_policy_response.raise_for_status.return_value = None

        mock_client_instance.post.side_effect = [
            mock_conv_response,
            mock_policy_response,
        ]
        mock_client_instance.get.return_value = mock_events_response

        mock_ws_instance = Mock()
        mock_ws_client.return_value = mock_ws_instance

        # Create conversation and set policy
        conversation = RemoteConversation(agent=self.agent, workspace=self.workspace)
        policy = AlwaysConfirm()
        conversation.set_confirmation_policy(policy)

        # Verify policy API call
        expected_payload = {"policy": policy.model_dump()}
        mock_client_instance.post.assert_any_call(
            f"/api/conversations/{conversation_id}/confirmation_policy",
            json=expected_payload,
        )

    @patch(
        "openhands.sdk.conversation.impl.remote_conversation.WebSocketCallbackClient"
    )
    def test_remote_conversation_reject_pending_actions(self, mock_ws_client):
        """Test rejecting pending actions."""
        # Setup mocks
        mock_client_instance = self.setup_mock_client()

        conversation_id = str(uuid.uuid4())
        mock_conv_response = self.create_mock_conversation_response(conversation_id)
        mock_events_response = self.create_mock_events_response()
        mock_reject_response = Mock()
        mock_reject_response.raise_for_status.return_value = None

        mock_client_instance.post.side_effect = [
            mock_conv_response,
            mock_reject_response,
        ]
        mock_client_instance.get.return_value = mock_events_response

        mock_ws_instance = Mock()
        mock_ws_client.return_value = mock_ws_instance

        # Create conversation and reject actions
        conversation = RemoteConversation(agent=self.agent, workspace=self.workspace)
        conversation.reject_pending_actions("Custom rejection reason")

        # Verify reject API call
        expected_payload = {"accept": False, "reason": "Custom rejection reason"}
        mock_client_instance.post.assert_any_call(
            f"/api/conversations/{conversation_id}/events/respond_to_confirmation",
            json=expected_payload,
        )

    @patch(
        "openhands.sdk.conversation.impl.remote_conversation.WebSocketCallbackClient"
    )
    def test_remote_conversation_pause(self, mock_ws_client):
        """Test pausing the conversation."""
        # Setup mocks
        mock_client_instance = self.setup_mock_client()

        conversation_id = str(uuid.uuid4())
        mock_conv_response = self.create_mock_conversation_response(conversation_id)
        mock_events_response = self.create_mock_events_response()
        mock_pause_response = Mock()
        mock_pause_response.raise_for_status.return_value = None

        mock_client_instance.post.side_effect = [
            mock_conv_response,
            mock_pause_response,
        ]
        mock_client_instance.get.return_value = mock_events_response

        mock_ws_instance = Mock()
        mock_ws_client.return_value = mock_ws_instance

        # Create conversation and pause
        conversation = RemoteConversation(agent=self.agent, workspace=self.workspace)
        conversation.pause()

        # Verify pause API call
        mock_client_instance.post.assert_any_call(
            f"/api/conversations/{conversation_id}/pause"
        )

    @patch(
        "openhands.sdk.conversation.impl.remote_conversation.WebSocketCallbackClient"
    )
    def test_remote_conversation_update_secrets(self, mock_ws_client):
        """Test updating secrets."""
        # Setup mocks
        mock_client_instance = self.setup_mock_client()

        conversation_id = str(uuid.uuid4())
        mock_conv_response = self.create_mock_conversation_response(conversation_id)
        mock_events_response = self.create_mock_events_response()
        mock_secrets_response = Mock()
        mock_secrets_response.raise_for_status.return_value = None

        mock_client_instance.post.side_effect = [
            mock_conv_response,
            mock_secrets_response,
        ]
        mock_client_instance.get.return_value = mock_events_response

        mock_ws_instance = Mock()
        mock_ws_client.return_value = mock_ws_instance

        # Create conversation and update secrets
        conversation = RemoteConversation(agent=self.agent, workspace=self.workspace)

        # Test with string secrets
        from typing import cast

        from openhands.sdk.conversation.secrets_manager import SecretValue

        secrets = cast(
            dict[str, SecretValue],
            {
                "api_key": "secret_value",
                "token": "another_secret",
            },
        )
        conversation.update_secrets(secrets)

        # Verify secrets API call
        expected_payload = {"secrets": secrets}
        mock_client_instance.post.assert_any_call(
            f"/api/conversations/{conversation_id}/secrets",
            json=expected_payload,
        )

    @patch(
        "openhands.sdk.conversation.impl.remote_conversation.WebSocketCallbackClient"
    )
    def test_remote_conversation_update_secrets_callable(self, mock_ws_client):
        """Test updating secrets with callable values."""
        # Setup mocks
        mock_client_instance = self.setup_mock_client()

        conversation_id = str(uuid.uuid4())
        mock_conv_response = self.create_mock_conversation_response(conversation_id)
        mock_events_response = self.create_mock_events_response()
        mock_secrets_response = Mock()
        mock_secrets_response.raise_for_status.return_value = None

        mock_client_instance.post.side_effect = [
            mock_conv_response,
            mock_secrets_response,
        ]
        mock_client_instance.get.return_value = mock_events_response

        mock_ws_instance = Mock()
        mock_ws_client.return_value = mock_ws_instance

        # Create conversation and update secrets with callable
        conversation = RemoteConversation(agent=self.agent, workspace=self.workspace)

        def get_secret():
            return "callable_secret_value"

        secrets: dict[str, SecretValue] = {
            "api_key": "string_secret",
            "callable_secret": get_secret,  # type: ignore[dict-item]
        }
        conversation.update_secrets(secrets)

        # Verify secrets API call with resolved callable
        expected_payload = {
            "secrets": {
                "api_key": "string_secret",
                "callable_secret": "callable_secret_value",
            }
        }
        mock_client_instance.post.assert_any_call(
            f"/api/conversations/{conversation_id}/secrets",
            json=expected_payload,
        )

    @patch(
        "openhands.sdk.conversation.impl.remote_conversation.WebSocketCallbackClient"
    )
    def test_remote_conversation_close(self, mock_ws_client):
        """Test closing the conversation."""
        # Setup mocks
        mock_client_instance = self.setup_mock_client()

        conversation_id = str(uuid.uuid4())
        mock_conv_response = self.create_mock_conversation_response(conversation_id)
        mock_events_response = self.create_mock_events_response()

        mock_client_instance.post.return_value = mock_conv_response
        mock_client_instance.get.return_value = mock_events_response

        mock_ws_instance = Mock()
        mock_ws_client.return_value = mock_ws_instance

        # Create conversation and close
        conversation = RemoteConversation(agent=self.agent, workspace=self.workspace)
        conversation.close()

        # Verify WebSocket client was stopped
        mock_ws_instance.stop.assert_called_once()

        # Verify HTTP client was closed
        mock_client_instance.close.assert_called_once()

    @patch(
        "openhands.sdk.conversation.impl.remote_conversation.WebSocketCallbackClient"
    )
    def test_remote_conversation_stuck_detector_not_implemented(self, mock_ws_client):
        """Test that stuck_detector property raises NotImplementedError."""
        # Setup mocks
        mock_client_instance = self.setup_mock_client()

        conversation_id = str(uuid.uuid4())
        mock_conv_response = self.create_mock_conversation_response(conversation_id)
        mock_events_response = self.create_mock_events_response()

        mock_client_instance.post.return_value = mock_conv_response
        mock_client_instance.get.return_value = mock_events_response

        mock_ws_instance = Mock()
        mock_ws_client.return_value = mock_ws_instance

        # Create conversation
        conversation = RemoteConversation(agent=self.agent, workspace=self.workspace)

        # Accessing stuck_detector should raise NotImplementedError
        with pytest.raises(
            NotImplementedError, match="stuck detection is not available"
        ):
            _ = conversation.stuck_detector

    @patch(
        "openhands.sdk.conversation.impl.remote_conversation.WebSocketCallbackClient"
    )
    def test_remote_conversation_with_callbacks(self, mock_ws_client):
        """Test RemoteConversation with custom callbacks."""
        # Setup mocks
        mock_client_instance = self.setup_mock_client()

        conversation_id = str(uuid.uuid4())
        mock_conv_response = self.create_mock_conversation_response(conversation_id)
        mock_events_response = self.create_mock_events_response()

        mock_client_instance.post.return_value = mock_conv_response
        mock_client_instance.get.return_value = mock_events_response

        mock_ws_instance = Mock()
        mock_ws_client.return_value = mock_ws_instance

        # Create custom callback
        callback_calls = []

        def custom_callback(event):
            callback_calls.append(event)

        # Create conversation with callback
        _conversation = RemoteConversation(
            agent=self.agent,
            workspace=self.workspace,
            callbacks=[custom_callback],
        )

        # Verify WebSocket client was created with callback
        # The callback should be a composed callback that includes the custom callback
        mock_ws_client.assert_called_once()
        call_args = mock_ws_client.call_args
        assert "callback" in call_args[1]  # Should have a callback parameter

    @patch(
        "openhands.sdk.conversation.impl.remote_conversation.WebSocketCallbackClient"
    )
    def test_remote_conversation_with_visualize(self, mock_ws_client):
        """Test RemoteConversation with visualize=True."""
        # Setup mocks
        mock_client_instance = self.setup_mock_client()

        conversation_id = str(uuid.uuid4())
        mock_conv_response = self.create_mock_conversation_response(conversation_id)
        mock_events_response = self.create_mock_events_response()

        mock_client_instance.post.return_value = mock_conv_response
        mock_client_instance.get.return_value = mock_events_response

        mock_ws_instance = Mock()
        mock_ws_client.return_value = mock_ws_instance

        # Mock the visualizer
        with patch(
            "openhands.sdk.conversation.impl.remote_conversation.create_default_visualizer"
        ) as mock_visualizer:
            mock_viz_instance = Mock()
            mock_viz_instance.on_event = Mock()
            mock_visualizer.return_value = mock_viz_instance

            # Create conversation with visualize=True
            conversation = RemoteConversation(
                agent=self.agent,
                workspace=self.workspace,
                visualize=True,
            )

            # Verify visualizer was created and callback added
            mock_visualizer.assert_called_once()
            assert conversation._visualizer is mock_viz_instance

    @patch(
        "openhands.sdk.conversation.impl.remote_conversation.WebSocketCallbackClient"
    )
    def test_remote_conversation_host_url_normalization(self, mock_ws_client):
        """Test that host URL is normalized correctly."""
        # Setup mocks
        mock_client_instance = self.setup_mock_client()

        conversation_id = str(uuid.uuid4())
        mock_conv_response = self.create_mock_conversation_response(conversation_id)
        mock_events_response = self.create_mock_events_response()

        mock_client_instance.post.return_value = mock_conv_response
        mock_client_instance.get.return_value = mock_events_response

        mock_ws_instance = Mock()
        mock_ws_client.return_value = mock_ws_instance

        # Test with trailing slash
        host_with_slash = "http://localhost:8000/"
        workspace_with_slash = RemoteWorkspace(host=host_with_slash, working_dir="/tmp")
        workspace_with_slash._client = mock_client_instance
        conversation = RemoteConversation(
            agent=self.agent, workspace=workspace_with_slash
        )

        # Verify trailing slash was removed and workspace host was normalized
        assert conversation.workspace.host == "http://localhost:8000"
