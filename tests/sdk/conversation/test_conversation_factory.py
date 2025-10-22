"""Tests for Conversation factory functionality."""

import uuid
from unittest.mock import Mock, patch

from pydantic import SecretStr

from openhands.sdk import Conversation
from openhands.sdk.conversation.impl.local_conversation import LocalConversation
from openhands.sdk.conversation.impl.remote_conversation import RemoteConversation
from openhands.sdk.llm import LLM
from openhands.sdk.workspace import RemoteWorkspace


class TestConversationFactory:
    """Test Conversation factory functionality."""

    def setup_method(self):
        """Set up test environment."""
        from openhands.sdk import Agent

        self.llm: LLM = LLM(model="gpt-4", api_key=SecretStr("test-key"))
        self.agent: Agent = Agent(llm=self.llm, tools=[])

    def test_conversation_factory_returns_local_conversation(self):
        """Test that Conversation factory returns LocalConversation when no host is provided."""  # noqa: E501
        conversation = Conversation(agent=self.agent)

        assert isinstance(conversation, LocalConversation)
        assert not isinstance(conversation, RemoteConversation)

    @patch(
        "openhands.sdk.conversation.impl.remote_conversation.WebSocketCallbackClient"
    )
    def test_conversation_factory_returns_remote_conversation(self, mock_ws_client):
        """Test that Conversation factory returns RemoteConversation when host is provided."""  # noqa: E501
        workspace = RemoteWorkspace(
            host="http://localhost:8000", working_dir="/workspace/project"
        )

        # Mock the workspace client directly
        mock_client_instance = Mock()
        workspace._client = mock_client_instance

        # Mock conversation creation response
        conversation_id = str(uuid.uuid4())
        mock_conv_response = Mock()
        mock_conv_response.raise_for_status.return_value = None
        mock_conv_response.json.return_value = {"id": conversation_id}

        # Mock events response
        mock_events_response = Mock()
        mock_events_response.raise_for_status.return_value = None
        mock_events_response.json.return_value = {"items": [], "next_page_id": None}

        mock_client_instance.request.side_effect = [
            mock_conv_response,
            mock_events_response,
        ]

        # Mock WebSocket client
        _mock_ws_instance = mock_ws_client.return_value

        conversation = Conversation(agent=self.agent, workspace=workspace)

        assert isinstance(conversation, RemoteConversation)
        assert not isinstance(conversation, LocalConversation)

    def test_conversation_factory_local_with_all_parameters(self):
        """Test LocalConversation creation with all parameters."""
        conversation = Conversation(
            agent=self.agent,
            conversation_id=None,
            callbacks=[],
            max_iteration_per_run=100,
            stuck_detection=False,
            visualize=False,
        )

        assert isinstance(conversation, LocalConversation)
        assert conversation.max_iteration_per_run == 100

    @patch(
        "openhands.sdk.conversation.impl.remote_conversation.WebSocketCallbackClient"
    )
    def test_conversation_factory_remote_with_all_parameters(self, mock_ws_client):
        """Test RemoteConversation creation with all parameters."""
        workspace = RemoteWorkspace(
            host="http://localhost:8000", working_dir="/workspace/project"
        )

        # Mock the workspace client directly
        mock_client_instance = Mock()
        workspace._client = mock_client_instance

        # Mock conversation creation response
        mock_conv_response = Mock()
        mock_conv_response.raise_for_status.return_value = None
        mock_conv_response.json.return_value = {"id": str(uuid.uuid4())}

        # Mock events response
        mock_events_response = Mock()
        mock_events_response.raise_for_status.return_value = None
        mock_events_response.json.return_value = {"items": [], "next_page_id": None}

        mock_client_instance.request.side_effect = [
            mock_conv_response,
            mock_events_response,
        ]

        # Mock WebSocket client
        _mock_ws_instance = mock_ws_client.return_value

        conversation = Conversation(
            agent=self.agent,
            workspace=workspace,
            conversation_id=None,
            callbacks=[],
            max_iteration_per_run=200,
            stuck_detection=True,
            visualize=True,
        )

        assert isinstance(conversation, RemoteConversation)
        assert conversation.max_iteration_per_run == 200

    def test_conversation_factory_type_hints(self):
        """Test that type hints work correctly for the factory."""
        # This test verifies that the overloads work correctly
        # In practice, type checkers should be able to infer the correct return type

        # Local conversation (no host parameter)
        local_conv = Conversation(agent=self.agent)
        # Type checker should infer this as LocalConversation

        # Remote conversation (with host parameter)
        with patch(
            "openhands.sdk.conversation.impl.remote_conversation.WebSocketCallbackClient"
        ):
            workspace = RemoteWorkspace(
                host="http://localhost:8000", working_dir="/workspace/project"
            )

            # Mock the workspace client directly
            mock_client_instance = Mock()
            workspace._client = mock_client_instance

            # Mock conversation creation response
            mock_conv_response = Mock()
            mock_conv_response.raise_for_status.return_value = None
            mock_conv_response.json.return_value = {"id": str(uuid.uuid4())}

            # Mock events response
            mock_events_response = Mock()
            mock_events_response.raise_for_status.return_value = None
            mock_events_response.json.return_value = {"items": [], "next_page_id": None}

            mock_client_instance.request.side_effect = [
                mock_conv_response,
                mock_events_response,
            ]

            remote_conv = Conversation(agent=self.agent, workspace=workspace)
            # Type checker should infer this as RemoteConversation

        # Runtime verification
        assert isinstance(local_conv, LocalConversation)
        assert isinstance(remote_conv, RemoteConversation)

    def test_conversation_factory_string_workspace_creates_local(self):
        """Test that string workspace creates LocalConversation."""
        conversation = Conversation(agent=self.agent, workspace="")

        # String workspace should create LocalConversation
        assert isinstance(conversation, LocalConversation)

    def test_conversation_factory_default_workspace_creates_local(self):
        """Test that default workspace creates LocalConversation."""
        conversation = Conversation(agent=self.agent)

        assert isinstance(conversation, LocalConversation)

    @patch(
        "openhands.sdk.conversation.impl.remote_conversation.WebSocketCallbackClient"
    )
    def test_conversation_factory_remote_workspace_creates_remote(self, mock_ws_client):
        """Test that RemoteWorkspace creates RemoteConversation."""
        workspace = RemoteWorkspace(host="   ", working_dir="/workspace/project")

        # Mock the workspace client directly
        mock_client_instance = Mock()
        workspace._client = mock_client_instance

        # Mock conversation creation response
        mock_conv_response = Mock()
        mock_conv_response.raise_for_status.return_value = None
        mock_conv_response.json.return_value = {"id": str(uuid.uuid4())}

        # Mock events response
        mock_events_response = Mock()
        mock_events_response.raise_for_status.return_value = None
        mock_events_response.json.return_value = {"items": [], "next_page_id": None}

        mock_client_instance.request.side_effect = [
            mock_conv_response,
            mock_events_response,
        ]

        # Mock WebSocket client
        _mock_ws_instance = mock_ws_client.return_value

        conversation = Conversation(agent=self.agent, workspace=workspace)

        # RemoteWorkspace should create RemoteConversation
        assert isinstance(conversation, RemoteConversation)
