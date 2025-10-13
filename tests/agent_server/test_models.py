"""Tests for agent_server models."""

import pytest
from pydantic import ValidationError

from openhands.agent_server.models import SendMessageRequest
from openhands.sdk.llm.message import TextContent


class TestSendMessageRequest:
    """Test cases for SendMessageRequest model."""

    def test_send_message_request_default_values(self):
        """Test SendMessageRequest with default values."""
        request = SendMessageRequest()
        
        assert request.role == "user"
        assert request.content == []
        assert request.run is True  # Default should be True

    def test_send_message_request_with_content(self):
        """Test SendMessageRequest with content."""
        content = [TextContent(text="Hello, world!")]
        request = SendMessageRequest(content=content)
        
        assert request.role == "user"
        assert request.content == content
        assert request.run is True

    def test_send_message_request_with_run_false(self):
        """Test SendMessageRequest with run=False."""
        request = SendMessageRequest(run=False)
        
        assert request.role == "user"
        assert request.content == []
        assert request.run is False

    def test_send_message_request_with_run_true(self):
        """Test SendMessageRequest with run=True explicitly."""
        request = SendMessageRequest(run=True)
        
        assert request.role == "user"
        assert request.content == []
        assert request.run is True

    def test_send_message_request_all_fields(self):
        """Test SendMessageRequest with all fields specified."""
        content = [TextContent(text="Test message")]
        request = SendMessageRequest(
            role="assistant",
            content=content,
            run=False
        )
        
        assert request.role == "assistant"
        assert request.content == content
        assert request.run is False

    def test_send_message_request_invalid_role(self):
        """Test SendMessageRequest with invalid role."""
        with pytest.raises(ValidationError):
            SendMessageRequest(role="invalid_role")

    def test_send_message_request_create_message(self):
        """Test create_message method."""
        content = [TextContent(text="Test message")]
        request = SendMessageRequest(
            role="user",
            content=content,
            run=False
        )
        
        message = request.create_message()
        
        assert message.role == "user"
        assert message.content == content
        # Note: The run field is not part of the Message object

    def test_send_message_request_from_dict(self):
        """Test creating SendMessageRequest from dictionary."""
        data = {
            "role": "system",
            "content": [{"text": "System message"}],
            "run": False
        }
        
        request = SendMessageRequest.model_validate(data)
        
        assert request.role == "system"
        assert len(request.content) == 1
        assert request.content[0].text == "System message"
        assert request.run is False

    def test_send_message_request_to_dict(self):
        """Test converting SendMessageRequest to dictionary."""
        content = [TextContent(text="Test message")]
        request = SendMessageRequest(
            role="user",
            content=content,
            run=True
        )
        
        data = request.model_dump()
        
        assert data["role"] == "user"
        assert len(data["content"]) == 1
        assert data["content"][0]["text"] == "Test message"
        assert data["content"][0]["type"] == "text"
        assert data["run"] is True

    def test_send_message_request_run_field_description(self):
        """Test that the run field has the correct description."""
        schema = SendMessageRequest.model_json_schema()
        run_field = schema["properties"]["run"]
        
        expected_description = (
            "Whether the agent loop should automatically run if not running"
        )
        assert run_field["description"] == expected_description
        assert run_field["default"] is True
        assert run_field["type"] == "boolean"