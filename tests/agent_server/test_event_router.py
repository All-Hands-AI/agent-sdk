"""Tests for event_router.py endpoints."""

from typing import cast
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from openhands.agent_server.event_router import event_router
from openhands.agent_server.event_service import EventService
from openhands.sdk import Message
from openhands.sdk.llm.message import TextContent


@pytest.fixture
def client():
    """Create a test client for the FastAPI app without authentication."""
    app = FastAPI()
    app.include_router(event_router, prefix="/api")
    return TestClient(app)


@pytest.fixture
def sample_conversation_id():
    """Return a sample conversation ID."""
    return uuid4()


@pytest.fixture
def mock_event_service():
    """Create a mock EventService for testing."""
    service = AsyncMock(spec=EventService)
    service.send_message = AsyncMock()
    return service


class TestSendMessageEndpoint:
    """Test cases for the send_message endpoint."""

    @pytest.mark.asyncio
    async def test_send_message_with_run_true(
        self, client, sample_conversation_id, mock_event_service
    ):
        """Test send_message endpoint with run=True."""
        with patch(
            "openhands.agent_server.event_router.conversation_service"
        ) as mock_conv_service:
            mock_conv_service.get_event_service = AsyncMock(
                return_value=mock_event_service
            )

            request_data = {
                "role": "user",
                "content": [{"type": "text", "text": "Hello, world!"}],
                "run": True,
            }

            response = client.post(
                f"/api/conversations/{sample_conversation_id}/events", json=request_data
            )

            assert response.status_code == 200
            assert response.json() == {"success": True}

            # Verify send_message was called with correct parameters
            mock_event_service.send_message.assert_called_once()
            call_args = mock_event_service.send_message.call_args
            message, run_flag = call_args[0]

            assert isinstance(message, Message)
            assert message.role == "user"
            assert len(message.content) == 1
            assert isinstance(message.content[0], TextContent)
            assert message.content[0].text == "Hello, world!"
            assert run_flag is True

    @pytest.mark.asyncio
    async def test_send_message_with_run_false(
        self, client, sample_conversation_id, mock_event_service
    ):
        """Test send_message endpoint with run=False."""
        with patch(
            "openhands.agent_server.event_router.conversation_service"
        ) as mock_conv_service:
            mock_conv_service.get_event_service = AsyncMock(
                return_value=mock_event_service
            )

            request_data = {
                "role": "assistant",
                "content": [{"type": "text", "text": "I understand."}],
                "run": False,
            }

            response = client.post(
                f"/api/conversations/{sample_conversation_id}/events", json=request_data
            )

            assert response.status_code == 200
            assert response.json() == {"success": True}

            # Verify send_message was called with run=False
            mock_event_service.send_message.assert_called_once()
            call_args = mock_event_service.send_message.call_args
            message, run_flag = call_args[0]

            assert isinstance(message, Message)
            assert message.role == "assistant"
            assert run_flag is False

    @pytest.mark.asyncio
    async def test_send_message_default_run_value(
        self, client, sample_conversation_id, mock_event_service
    ):
        """Test send_message endpoint with default run value."""
        with patch(
            "openhands.agent_server.event_router.conversation_service"
        ) as mock_conv_service:
            mock_conv_service.get_event_service = AsyncMock(
                return_value=mock_event_service
            )

            # Request without run field should use default value
            request_data = {
                "role": "user",
                "content": [{"type": "text", "text": "Test message"}],
            }

            response = client.post(
                f"/api/conversations/{sample_conversation_id}/events", json=request_data
            )

            assert response.status_code == 200
            assert response.json() == {"success": True}

            # Verify send_message was called with default run value (False)
            mock_event_service.send_message.assert_called_once()
            call_args = mock_event_service.send_message.call_args
            message, run_flag = call_args[0]

            assert isinstance(message, Message)
            assert message.role == "user"
            assert run_flag is False  # Default value from SendMessageRequest

    @pytest.mark.asyncio
    async def test_send_message_conversation_not_found(
        self, client, sample_conversation_id
    ):
        """Test send_message endpoint when conversation is not found."""
        with patch(
            "openhands.agent_server.event_router.conversation_service"
        ) as mock_conv_service:
            mock_conv_service.get_event_service = AsyncMock(return_value=None)

            request_data = {
                "role": "user",
                "content": [{"type": "text", "text": "Hello"}],
                "run": True,
            }

            response = client.post(
                f"/api/conversations/{sample_conversation_id}/events", json=request_data
            )

            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_send_message_with_different_content_types(
        self, client, sample_conversation_id, mock_event_service
    ):
        """Test send_message endpoint with different content types."""
        with patch(
            "openhands.agent_server.event_router.conversation_service"
        ) as mock_conv_service:
            mock_conv_service.get_event_service = AsyncMock(
                return_value=mock_event_service
            )

            # Test with multiple content items
            request_data = {
                "role": "user",
                "content": [
                    {"type": "text", "text": "First part"},
                    {"type": "text", "text": "Second part"},
                ],
                "run": False,
            }

            response = client.post(
                f"/api/conversations/{sample_conversation_id}/events", json=request_data
            )

            assert response.status_code == 200
            assert response.json() == {"success": True}

            # Verify message content was parsed correctly
            mock_event_service.send_message.assert_called_once()
            call_args = mock_event_service.send_message.call_args
            message, run_flag = call_args[0]

            assert isinstance(message, Message)
            assert message.role == "user"
            assert len(message.content) == 2
            assert all(isinstance(content, TextContent) for content in message.content)
            text_content = cast(list[TextContent], message.content)
            assert text_content[0].text == "First part"
            assert text_content[1].text == "Second part"
            assert run_flag is False

    @pytest.mark.asyncio
    async def test_send_message_with_system_role(
        self, client, sample_conversation_id, mock_event_service
    ):
        """Test send_message endpoint with system role."""
        with patch(
            "openhands.agent_server.event_router.conversation_service"
        ) as mock_conv_service:
            mock_conv_service.get_event_service = AsyncMock(
                return_value=mock_event_service
            )

            request_data = {
                "role": "system",
                "content": [{"type": "text", "text": "System initialization message"}],
                "run": True,
            }

            response = client.post(
                f"/api/conversations/{sample_conversation_id}/events", json=request_data
            )

            assert response.status_code == 200
            assert response.json() == {"success": True}

            # Verify system message was processed correctly
            mock_event_service.send_message.assert_called_once()
            call_args = mock_event_service.send_message.call_args
            message, run_flag = call_args[0]

            assert isinstance(message, Message)
            assert message.role == "system"
            assert run_flag is True

    @pytest.mark.asyncio
    async def test_send_message_invalid_request_data(
        self, client, sample_conversation_id
    ):
        """Test send_message endpoint with invalid request data."""
        # Test with invalid role value
        invalid_role_data = {
            "role": "invalid_role",
            "content": [{"type": "text", "text": "Hello"}],
            "run": True,
        }

        response = client.post(
            f"/api/conversations/{sample_conversation_id}/events",
            json=invalid_role_data,
        )

        assert response.status_code == 422  # Validation error

        # Test with invalid content structure
        invalid_content_data = {
            "role": "user",
            "content": "invalid_content_should_be_list",  # Should be a list
            "run": True,
        }

        response = client.post(
            f"/api/conversations/{sample_conversation_id}/events",
            json=invalid_content_data,
        )

        assert response.status_code == 422  # Validation error


class TestSearchEventsEndpoint:
    """Test cases for the search events endpoint with timestamp filtering."""

    @pytest.mark.asyncio
    async def test_search_events_with_naive_datetime(
        self, client, sample_conversation_id, mock_event_service
    ):
        """Test search events with naive datetime (no timezone)."""
        with patch(
            "openhands.agent_server.event_router.conversation_service"
        ) as mock_conv_service:
            mock_conv_service.get_event_service = AsyncMock(
                return_value=mock_event_service
            )

            # Mock the search_events method to return a sample result
            mock_event_service.search_events = AsyncMock(
                return_value={"items": [], "next_page_id": None}
            )

            # Test with naive datetime
            response = client.get(
                f"/api/conversations/{sample_conversation_id}/events/search",
                params={
                    "timestamp__gte": "2025-01-01T12:00:00",  # Naive datetime string
                    "limit": 10,
                },
            )

            assert response.status_code == 200
            mock_event_service.search_events.assert_called_once()
            # Verify that the datetime was normalized (converted to datetime object)
            call_args = mock_event_service.search_events.call_args
            # Check positional arguments: (page_id, limit, kind, sort_order,
            # timestamp__gte, timestamp__lt)
            assert len(call_args[0]) >= 5  # Should have at least 5 positional args
            assert call_args[0][4] is not None  # timestamp__gte should be normalized
            assert call_args[0][5] is None  # timestamp__lt should be None

    @pytest.mark.asyncio
    async def test_search_events_with_timezone_aware_datetime(
        self, client, sample_conversation_id, mock_event_service
    ):
        """Test search events with timezone-aware datetime."""
        with patch(
            "openhands.agent_server.event_router.conversation_service"
        ) as mock_conv_service:
            mock_conv_service.get_event_service = AsyncMock(
                return_value=mock_event_service
            )

            # Mock the search_events method to return a sample result
            mock_event_service.search_events = AsyncMock(
                return_value={"items": [], "next_page_id": None}
            )

            # Test with timezone-aware datetime (UTC)
            response = client.get(
                f"/api/conversations/{sample_conversation_id}/events/search",
                params={
                    "timestamp__gte": "2025-01-01T12:00:00Z",  # UTC timezone
                    "limit": 10,
                },
            )

            assert response.status_code == 200
            mock_event_service.search_events.assert_called_once()
            # Verify that the datetime was normalized
            call_args = mock_event_service.search_events.call_args
            # Check positional arguments: (page_id, limit, kind, sort_order,
            # timestamp__gte, timestamp__lt)
            assert len(call_args[0]) >= 5  # Should have at least 5 positional args
            assert call_args[0][4] is not None  # timestamp__gte should be normalized
            assert call_args[0][5] is None  # timestamp__lt should be None

    @pytest.mark.asyncio
    async def test_search_events_with_timezone_range(
        self, client, sample_conversation_id, mock_event_service
    ):
        """Test search events with both timestamp filters using
        timezone-aware datetimes."""
        with patch(
            "openhands.agent_server.event_router.conversation_service"
        ) as mock_conv_service:
            mock_conv_service.get_event_service = AsyncMock(
                return_value=mock_event_service
            )

            # Mock the search_events method to return a sample result
            mock_event_service.search_events = AsyncMock(
                return_value={"items": [], "next_page_id": None}
            )

            # Test with both timestamp filters using timezone-aware datetimes
            response = client.get(
                f"/api/conversations/{sample_conversation_id}/events/search",
                params={
                    "timestamp__gte": "2025-01-01T10:00:00+05:00",  # UTC+5
                    "timestamp__lt": "2025-01-01T14:00:00-08:00",  # UTC-8
                    "limit": 10,
                },
            )

            assert response.status_code == 200
            mock_event_service.search_events.assert_called_once()
            # Verify that both datetimes were normalized
            call_args = mock_event_service.search_events.call_args
            # Check positional arguments: (page_id, limit, kind, sort_order,
            # timestamp__gte, timestamp__lt)
            assert len(call_args[0]) >= 6  # Should have at least 6 positional args
            assert call_args[0][4] is not None  # timestamp__gte should be normalized
            assert call_args[0][5] is not None  # timestamp__lt should be normalized

    @pytest.mark.asyncio
    async def test_count_events_with_timezone_aware_datetime(
        self, client, sample_conversation_id, mock_event_service
    ):
        """Test count events with timezone-aware datetime."""
        with patch(
            "openhands.agent_server.event_router.conversation_service"
        ) as mock_conv_service:
            mock_conv_service.get_event_service = AsyncMock(
                return_value=mock_event_service
            )

            # Mock the count_events method to return a sample result
            mock_event_service.count_events = AsyncMock(return_value=5)

            # Test with timezone-aware datetime
            response = client.get(
                f"/api/conversations/{sample_conversation_id}/events/count",
                params={
                    "timestamp__gte": "2025-01-01T12:00:00+02:00",  # UTC+2
                },
            )

            assert response.status_code == 200
            assert response.json() == 5
            mock_event_service.count_events.assert_called_once()
            # Verify that the datetime was normalized
            call_args = mock_event_service.count_events.call_args
            # Check positional arguments: (kind, timestamp__gte, timestamp__lt)
            assert len(call_args[0]) >= 2  # Should have at least 2 positional args
            assert call_args[0][1] is not None  # timestamp__gte should be normalized
            assert call_args[0][2] is None  # timestamp__lt should be None

    @pytest.mark.asyncio
    async def test_search_events_timezone_normalization_consistency(
        self, client, sample_conversation_id, mock_event_service
    ):
        """Test that different timezone representations of the same moment
        normalize consistently."""
        with patch(
            "openhands.agent_server.event_router.conversation_service"
        ) as mock_conv_service:
            mock_conv_service.get_event_service = AsyncMock(
                return_value=mock_event_service
            )

            # Mock the search_events method to return a sample result
            mock_event_service.search_events = AsyncMock(
                return_value={"items": [], "next_page_id": None}
            )

            # Test 1: UTC timezone
            response1 = client.get(
                f"/api/conversations/{sample_conversation_id}/events/search",
                params={
                    "timestamp__gte": "2025-01-01T12:00:00Z",  # 12:00 UTC
                    "limit": 10,
                },
            )

            # Test 2: EST timezone (UTC-5) - same moment as 12:00 UTC
            response2 = client.get(
                f"/api/conversations/{sample_conversation_id}/events/search",
                params={
                    # 07:00 EST = 12:00 UTC
                    "timestamp__gte": "2025-01-01T07:00:00-05:00",
                    "limit": 10,
                },
            )

            assert response1.status_code == 200
            assert response2.status_code == 200

            # Both calls should have been made
            assert mock_event_service.search_events.call_count == 2

            # Get the normalized datetimes from both calls
            call1_args = mock_event_service.search_events.call_args_list[0]
            call2_args = mock_event_service.search_events.call_args_list[1]

            # Both should normalize to the same server time
            # Check positional arguments: (page_id, limit, kind, sort_order,
            # timestamp__gte, timestamp__lt)
            normalized_time1 = call1_args[0][4]  # timestamp__gte from first call
            normalized_time2 = call2_args[0][4]  # timestamp__gte from second call

            # They should be the same after normalization
            assert normalized_time1 == normalized_time2
