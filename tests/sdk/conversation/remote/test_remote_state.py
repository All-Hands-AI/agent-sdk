"""Tests for RemoteState."""

import uuid
from unittest.mock import Mock

import httpx
import pytest
from pydantic import SecretStr

from openhands.sdk.agent import Agent
from openhands.sdk.conversation.impl.remote_conversation import RemoteState
from openhands.sdk.conversation.state import AgentExecutionStatus
from openhands.sdk.llm import LLM
from openhands.sdk.security.confirmation_policy import AlwaysConfirm


class TestRemoteState:
    """Test RemoteState functionality."""

    def setup_method(self):
        """Set up test environment."""
        self.mock_client = Mock(spec=httpx.Client)
        self.conversation_id = str(uuid.uuid4())

    def create_mock_conversation_info(self, **overrides):
        """Create mock conversation info response."""
        # Create a basic agent for testing
        llm = LLM(model="gpt-4", api_key=SecretStr("test-key"))
        agent = Agent(llm=llm, tools=[])

        default_info = {
            "id": self.conversation_id,
            "agent_status": "running",
            "confirmation_policy": {"kind": "NeverConfirm"},
            "activated_knowledge_microagents": [],
            "agent": agent.model_dump(mode="json"),
        }
        default_info.update(overrides)
        return default_info

    def create_mock_api_response(self, data):
        """Create a mock API response."""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = data
        return mock_response

    def test_remote_state_initialization(self):
        """Test RemoteState initialization."""
        # Mock the initial API call for events
        mock_events_response = Mock()
        mock_events_response.raise_for_status.return_value = None
        mock_events_response.json.return_value = {"items": [], "next_page_id": None}
        self.mock_client.get.return_value = mock_events_response

        state = RemoteState(self.mock_client, self.conversation_id)

        assert state._client == self.mock_client
        assert state._conversation_id == self.conversation_id
        assert hasattr(state, "_events")

        # Verify events API was called during initialization
        self.mock_client.get.assert_called_with(
            f"/api/conversations/{self.conversation_id}/events/search",
            params={"limit": 100},
        )

    def test_remote_state_id_property(self):
        """Test RemoteState id property."""
        # Mock events API call
        mock_events_response = Mock()
        mock_events_response.raise_for_status.return_value = None
        mock_events_response.json.return_value = {"items": [], "next_page_id": None}
        self.mock_client.get.return_value = mock_events_response

        state = RemoteState(self.mock_client, self.conversation_id)

        conversation_uuid = state.id
        assert isinstance(conversation_uuid, uuid.UUID)
        assert str(conversation_uuid) == self.conversation_id

    def test_remote_state_events_property(self):
        """Test RemoteState events property."""
        # Mock events API call
        mock_events_response = Mock()
        mock_events_response.raise_for_status.return_value = None
        mock_events_response.json.return_value = {"items": [], "next_page_id": None}
        self.mock_client.get.return_value = mock_events_response

        state = RemoteState(self.mock_client, self.conversation_id)

        events = state.events
        assert hasattr(events, "__len__")
        assert hasattr(events, "__getitem__")
        assert hasattr(events, "__iter__")

    def test_remote_state_agent_status_property(self):
        """Test RemoteState agent_status property."""
        # Mock events API call
        mock_events_response = Mock()
        mock_events_response.raise_for_status.return_value = None
        mock_events_response.json.return_value = {"items": [], "next_page_id": None}

        # Mock conversation info API call
        conversation_info = self.create_mock_conversation_info(agent_status="running")
        mock_info_response = self.create_mock_api_response(conversation_info)

        self.mock_client.get.side_effect = [mock_events_response, mock_info_response]

        state = RemoteState(self.mock_client, self.conversation_id)
        agent_status = state.agent_status

        assert agent_status == AgentExecutionStatus.RUNNING

        # Verify conversation info API was called
        self.mock_client.get.assert_any_call(
            f"/api/conversations/{self.conversation_id}"
        )

    def test_remote_state_agent_status_different_values(self):
        """Test RemoteState agent_status with different status values."""
        # Mock events API call
        mock_events_response = Mock()
        mock_events_response.raise_for_status.return_value = None
        mock_events_response.json.return_value = {"items": [], "next_page_id": None}

        test_statuses = ["running", "paused", "finished", "error"]

        for status in test_statuses:
            # Reset mock
            self.mock_client.reset_mock()
            self.mock_client.get.side_effect = None

            conversation_info = self.create_mock_conversation_info(agent_status=status)
            mock_info_response = self.create_mock_api_response(conversation_info)
            self.mock_client.get.side_effect = [
                mock_events_response,
                mock_info_response,
            ]

            state = RemoteState(self.mock_client, self.conversation_id)
            agent_status = state.agent_status

            assert agent_status == AgentExecutionStatus(status)

    def test_remote_state_agent_status_missing(self):
        """Test RemoteState agent_status when missing from response."""
        # Mock events API call
        mock_events_response = Mock()
        mock_events_response.raise_for_status.return_value = None
        mock_events_response.json.return_value = {"items": [], "next_page_id": None}

        # Mock conversation info without agent_status
        conversation_info = self.create_mock_conversation_info()
        del conversation_info["agent_status"]
        mock_info_response = self.create_mock_api_response(conversation_info)

        self.mock_client.get.side_effect = [mock_events_response, mock_info_response]

        state = RemoteState(self.mock_client, self.conversation_id)

        with pytest.raises(
            RuntimeError, match="agent_status missing in conversation info"
        ):
            _ = state.agent_status

    def test_remote_state_agent_status_setter_not_implemented(self):
        """Test that setting agent_status raises NotImplementedError."""
        # Mock events API call
        mock_events_response = Mock()
        mock_events_response.raise_for_status.return_value = None
        mock_events_response.json.return_value = {"items": [], "next_page_id": None}
        self.mock_client.get.return_value = mock_events_response

        state = RemoteState(self.mock_client, self.conversation_id)

        with pytest.raises(
            NotImplementedError,
            match="Setting agent_status on RemoteState has no effect",
        ):
            state.agent_status = AgentExecutionStatus.PAUSED

    def test_remote_state_confirmation_policy_property(self):
        """Test RemoteState confirmation_policy property."""
        # Mock events API call
        mock_events_response = Mock()
        mock_events_response.raise_for_status.return_value = None
        mock_events_response.json.return_value = {"items": [], "next_page_id": None}

        # Mock conversation info with confirmation policy
        conversation_info = self.create_mock_conversation_info(
            confirmation_policy={"kind": "AlwaysConfirm"}
        )
        mock_info_response = self.create_mock_api_response(conversation_info)

        self.mock_client.get.side_effect = [mock_events_response, mock_info_response]

        state = RemoteState(self.mock_client, self.conversation_id)
        policy = state.confirmation_policy

        assert isinstance(policy, AlwaysConfirm)

    def test_remote_state_confirmation_policy_missing(self):
        """Test RemoteState confirmation_policy when missing from response."""
        # Mock events API call
        mock_events_response = Mock()
        mock_events_response.raise_for_status.return_value = None
        mock_events_response.json.return_value = {"items": [], "next_page_id": None}

        # Mock conversation info without confirmation_policy
        conversation_info = self.create_mock_conversation_info()
        del conversation_info["confirmation_policy"]
        mock_info_response = self.create_mock_api_response(conversation_info)

        self.mock_client.get.side_effect = [mock_events_response, mock_info_response]

        state = RemoteState(self.mock_client, self.conversation_id)

        with pytest.raises(
            RuntimeError, match="confirmation_policy missing in conversation info"
        ):
            _ = state.confirmation_policy

    def test_remote_state_activated_knowledge_microagents_property(self):
        """Test RemoteState activated_knowledge_microagents property."""
        # Mock events API call
        mock_events_response = Mock()
        mock_events_response.raise_for_status.return_value = None
        mock_events_response.json.return_value = {"items": [], "next_page_id": None}

        # Mock conversation info with microagents
        microagents = ["agent1", "agent2", "agent3"]
        conversation_info = self.create_mock_conversation_info(
            activated_knowledge_microagents=microagents
        )
        mock_info_response = self.create_mock_api_response(conversation_info)

        self.mock_client.get.side_effect = [mock_events_response, mock_info_response]

        state = RemoteState(self.mock_client, self.conversation_id)
        result = state.activated_knowledge_microagents

        assert result == microagents

    def test_remote_state_activated_knowledge_microagents_empty(self):
        """Test RemoteState activated_knowledge_microagents when empty."""
        # Mock events API call
        mock_events_response = Mock()
        mock_events_response.raise_for_status.return_value = None
        mock_events_response.json.return_value = {"items": [], "next_page_id": None}

        # Mock conversation info without microagents (should default to empty list)
        conversation_info = self.create_mock_conversation_info()
        mock_info_response = self.create_mock_api_response(conversation_info)

        self.mock_client.get.side_effect = [mock_events_response, mock_info_response]

        state = RemoteState(self.mock_client, self.conversation_id)
        result = state.activated_knowledge_microagents

        assert result == []

    def test_remote_state_agent_property(self):
        """Test RemoteState agent property."""
        # Mock events API call
        mock_events_response = Mock()
        mock_events_response.raise_for_status.return_value = None
        mock_events_response.json.return_value = {"items": [], "next_page_id": None}

        # Mock conversation info with agent
        conversation_info = self.create_mock_conversation_info()
        mock_info_response = self.create_mock_api_response(conversation_info)

        self.mock_client.get.side_effect = [mock_events_response, mock_info_response]

        state = RemoteState(self.mock_client, self.conversation_id)
        agent = state.agent

        assert isinstance(agent, Agent)

    def test_remote_state_agent_missing(self):
        """Test RemoteState agent when missing from response."""
        # Mock events API call
        mock_events_response = Mock()
        mock_events_response.raise_for_status.return_value = None
        mock_events_response.json.return_value = {"items": [], "next_page_id": None}

        # Mock conversation info without agent
        conversation_info = self.create_mock_conversation_info()
        del conversation_info["agent"]
        mock_info_response = self.create_mock_api_response(conversation_info)

        self.mock_client.get.side_effect = [mock_events_response, mock_info_response]

        state = RemoteState(self.mock_client, self.conversation_id)

        with pytest.raises(RuntimeError, match="agent missing in conversation info"):
            _ = state.agent

    def test_remote_state_model_dump(self):
        """Test RemoteState model_dump method."""
        # Mock events API call
        mock_events_response = Mock()
        mock_events_response.raise_for_status.return_value = None
        mock_events_response.json.return_value = {"items": [], "next_page_id": None}

        # Mock conversation info
        conversation_info = self.create_mock_conversation_info()
        mock_info_response = self.create_mock_api_response(conversation_info)

        self.mock_client.get.side_effect = [mock_events_response, mock_info_response]

        state = RemoteState(self.mock_client, self.conversation_id)
        result = state.model_dump()

        assert result == conversation_info

    def test_remote_state_model_dump_json(self):
        """Test RemoteState model_dump_json method returns JSON string."""
        # Mock events API call
        mock_events_response = Mock()
        mock_events_response.raise_for_status.return_value = None
        mock_events_response.json.return_value = {"items": [], "next_page_id": None}

        # Mock conversation info
        conversation_info = self.create_mock_conversation_info()
        mock_info_response = self.create_mock_api_response(conversation_info)

        self.mock_client.get.side_effect = [mock_events_response, mock_info_response]

        state = RemoteState(self.mock_client, self.conversation_id)

        # Should serialize to JSON without raising
        json_str = state.model_dump_json()
        assert isinstance(json_str, str) and json_str.startswith("{")

    def test_remote_state_context_manager(self):
        """Test RemoteState context manager functionality."""
        # Mock events API call
        mock_events_response = Mock()
        mock_events_response.raise_for_status.return_value = None
        mock_events_response.json.return_value = {"items": [], "next_page_id": None}
        self.mock_client.get.return_value = mock_events_response

        state = RemoteState(self.mock_client, self.conversation_id)

        # Test context manager
        with state as ctx:
            assert ctx is state

        # Should not raise any exceptions

    def test_remote_state_api_error_handling(self):
        """Test error handling when conversation info API calls fail."""
        # Mock events API call (successful)
        mock_events_response = Mock()
        mock_events_response.raise_for_status.return_value = None
        mock_events_response.json.return_value = {"items": [], "next_page_id": None}

        # Mock conversation info API call (failure)
        mock_info_response = Mock()
        mock_info_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "API Error", request=Mock(), response=Mock()
        )

        self.mock_client.get.side_effect = [mock_events_response, mock_info_response]

        state = RemoteState(self.mock_client, self.conversation_id)

        # Should raise the HTTP error when accessing properties that need conversation info  # noqa: E501
        with pytest.raises(httpx.HTTPStatusError):
            _ = state.agent_status

    def test_remote_state_multiple_info_calls(self):
        """Test that multiple property accesses make separate API calls."""
        # Mock events API call
        mock_events_response = Mock()
        mock_events_response.raise_for_status.return_value = None
        mock_events_response.json.return_value = {"items": [], "next_page_id": None}

        # Mock conversation info API calls
        conversation_info = self.create_mock_conversation_info()
        mock_info_response = self.create_mock_api_response(conversation_info)

        # Set up side effects for multiple calls
        self.mock_client.get.side_effect = [
            mock_events_response,  # Initial events call
            mock_info_response,  # First info call
            mock_info_response,  # Second info call
        ]

        state = RemoteState(self.mock_client, self.conversation_id)

        # Access different properties
        _ = state.agent_status
        _ = state.confirmation_policy

        # Should have made 2 API calls total
        # (1 for events, 1 for info which gets cached)
        assert self.mock_client.get.call_count == 2
