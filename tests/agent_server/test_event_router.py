"""Tests for event_router.py endpoints."""

from typing import cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from openhands.agent_server import dependencies as deps
from openhands.agent_server.event_router import event_router
from openhands.agent_server.event_service import EventService
from openhands.sdk import Message
from openhands.sdk.llm.message import TextContent


def _client_with_override(conv_svc: AsyncMock) -> TestClient:
    app = FastAPI()
    app.include_router(event_router, prefix="/api")

    def _override_get_conversation_service(request: Request):
        return conv_svc

    app.dependency_overrides[deps.get_conversation_service] = (
        _override_get_conversation_service
    )
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
        self, sample_conversation_id, mock_event_service
    ) -> None:
        conv_svc = AsyncMock()
        conv_svc.get_event_service = AsyncMock(return_value=mock_event_service)
        client = _client_with_override(conv_svc)

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

        mock_event_service.send_message.assert_called_once()
        message, run_flag = mock_event_service.send_message.call_args[0]
        assert isinstance(message, Message)
        assert message.role == "user"
        assert len(message.content) == 1
        assert isinstance(message.content[0], TextContent)
        assert message.content[0].text == "Hello, world!"
        assert run_flag is True

    @pytest.mark.asyncio
    async def test_send_message_with_run_false(
        self, sample_conversation_id, mock_event_service
    ) -> None:
        conv_svc = AsyncMock()
        conv_svc.get_event_service = AsyncMock(return_value=mock_event_service)
        client = _client_with_override(conv_svc)

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

        mock_event_service.send_message.assert_called_once()
        message, run_flag = mock_event_service.send_message.call_args[0]
        assert isinstance(message, Message)
        assert message.role == "assistant"
        assert run_flag is False

    @pytest.mark.asyncio
    async def test_send_message_default_run_value(
        self, sample_conversation_id, mock_event_service
    ) -> None:
        conv_svc = AsyncMock()
        conv_svc.get_event_service = AsyncMock(return_value=mock_event_service)
        client = _client_with_override(conv_svc)

        request_data = {
            "role": "user",
            "content": [{"type": "text", "text": "Test message"}],
        }

        response = client.post(
            f"/api/conversations/{sample_conversation_id}/events", json=request_data
        )
        assert response.status_code == 200
        assert response.json() == {"success": True}

        mock_event_service.send_message.assert_called_once()
        message, run_flag = mock_event_service.send_message.call_args[0]
        assert isinstance(message, Message)
        assert message.role == "user"
        assert run_flag is False

    @pytest.mark.asyncio
    async def test_send_message_conversation_not_found(
        self, sample_conversation_id
    ) -> None:
        conv_svc = AsyncMock()
        conv_svc.get_event_service = AsyncMock(return_value=None)
        client = _client_with_override(conv_svc)

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
        self, sample_conversation_id, mock_event_service
    ) -> None:
        conv_svc = AsyncMock()
        conv_svc.get_event_service = AsyncMock(return_value=mock_event_service)
        client = _client_with_override(conv_svc)

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

        mock_event_service.send_message.assert_called_once()
        message, run_flag = mock_event_service.send_message.call_args[0]
        assert isinstance(message, Message)
        assert message.role == "user"
        assert len(message.content) == 2
        assert all(isinstance(c, TextContent) for c in message.content)
        text_content = cast(list[TextContent], message.content)
        assert text_content[0].text == "First part"
        assert text_content[1].text == "Second part"
        assert run_flag is False

    @pytest.mark.asyncio
    async def test_send_message_with_system_role(
        self, sample_conversation_id, mock_event_service
    ) -> None:
        conv_svc = AsyncMock()
        conv_svc.get_event_service = AsyncMock(return_value=mock_event_service)
        client = _client_with_override(conv_svc)

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

        mock_event_service.send_message.assert_called_once()
        message, run_flag = mock_event_service.send_message.call_args[0]
        assert isinstance(message, Message)
        assert message.role == "system"
        assert run_flag is True

    @pytest.mark.asyncio
    async def test_send_message_invalid_request_data(
        self, sample_conversation_id
    ) -> None:
        invalid_role_data = {
            "role": "invalid_role",
            "content": [{"type": "text", "text": "Hello"}],
            "run": True,
        }
        client = _client_with_override(AsyncMock())
        response = client.post(
            f"/api/conversations/{sample_conversation_id}/events",
            json=invalid_role_data,
        )
        assert response.status_code == 422

        invalid_content_data = {
            "role": "user",
            "content": "invalid_content_should_be_list",
            "run": True,
        }
        client = _client_with_override(AsyncMock())
        response = client.post(
            f"/api/conversations/{sample_conversation_id}/events",
            json=invalid_content_data,
        )
        assert response.status_code == 422
