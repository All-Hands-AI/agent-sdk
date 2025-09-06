"""Tests for LLM Responses API functionality."""

from unittest.mock import Mock, patch

import pytest

from openhands.sdk.llm.llm import LLM
from openhands.sdk.llm.message import Message


def test_is_responses_api_supported():
    """Test the is_responses_api_supported method."""
    # Test with a model that supports Responses API
    llm = LLM(model="o1-preview")
    assert llm.is_responses_api_supported()

    # Test with a model that doesn't support Responses API
    llm = LLM(model="gpt-3.5-turbo")
    assert not llm.is_responses_api_supported()


def test_responses_method_unsupported_model():
    """Test that responses method raises error for unsupported models."""
    llm = LLM(model="gpt-3.5-turbo")

    with pytest.raises(ValueError, match="does not support the Responses API"):
        llm.responses(input="Hello")


def test_responses_method_streaming_not_supported():
    """Test that responses method raises error when streaming is requested."""
    llm = LLM(model="o1-preview")

    with pytest.raises(ValueError, match="Streaming is not supported"):
        llm.responses(input="Hello", stream=True)


def test_responses_method_no_input():
    """Test that responses method raises error when no input is provided."""
    llm = LLM(model="o1-preview")

    with pytest.raises(
        ValueError, match="Either 'messages' or 'input' parameter must be provided"
    ):
        llm.responses()


@patch("openhands.sdk.llm.llm.litellm_responses")
def test_responses_method_with_input_string(mock_litellm_responses):
    """Test responses method with direct input string."""
    # Mock the litellm response
    mock_response = Mock()
    mock_response.id = "resp_123"
    mock_response.model = "o1-preview"
    mock_response.created = 1234567890
    mock_response.output = []
    # Add usage mock
    mock_usage = Mock()
    mock_usage.input_tokens = 10
    mock_usage.output_tokens = 20
    mock_usage.total_tokens = 30
    mock_response.usage = mock_usage
    mock_litellm_responses.return_value = mock_response

    llm = LLM(model="o1-preview")

    with patch.object(llm, "_telemetry") as mock_telemetry:
        mock_telemetry.log_enabled = False
        result = llm.responses(input="Hello, how are you?")

    # Verify litellm.responses was called correctly
    mock_litellm_responses.assert_called_once()
    call_args = mock_litellm_responses.call_args
    assert call_args[1]["input"] == "Hello, how are you?"
    assert call_args[1]["model"] == "o1-preview"

    # Verify result is a ModelResponse
    assert hasattr(result, "choices")
    assert len(result.choices) >= 1


@patch("openhands.sdk.llm.llm.litellm_responses")
def test_responses_method_with_messages_dict(mock_litellm_responses):
    """Test responses method with messages in dict format."""
    # Mock the litellm response
    mock_response = Mock()
    mock_response.id = "resp_456"
    mock_response.model = "o1-preview"
    mock_response.created = 1234567891
    mock_response.output = []
    # Add usage mock
    mock_usage = Mock()
    mock_usage.input_tokens = 15
    mock_usage.output_tokens = 25
    mock_usage.total_tokens = 40
    mock_response.usage = mock_usage
    mock_litellm_responses.return_value = mock_response

    llm = LLM(model="o1-preview")
    messages = [
        {"role": "user", "content": "What is 2+2?"},
        {"role": "assistant", "content": "2+2 equals 4."},
    ]

    with patch.object(llm, "_telemetry") as mock_telemetry:
        mock_telemetry.log_enabled = False
        llm.responses(messages=messages)

    # Verify litellm.responses was called
    mock_litellm_responses.assert_called_once()
    call_args = mock_litellm_responses.call_args

    # The input should be converted from messages format
    expected_input = "User: What is 2+2?\n\nAssistant: 2+2 equals 4."
    assert call_args[1]["input"] == expected_input

    # Verify the call was made correctly


@patch("openhands.sdk.llm.llm.litellm_responses")
def test_responses_method_with_message_objects(mock_litellm_responses):
    """Test responses method with Message objects."""
    # Mock the litellm response
    mock_response = Mock()
    mock_response.id = "resp_789"
    mock_response.model = "o1-preview"
    mock_response.created = 1234567892
    mock_response.output = []
    # Add usage mock
    mock_usage = Mock()
    mock_usage.input_tokens = 12
    mock_usage.output_tokens = 18
    mock_usage.total_tokens = 30
    mock_response.usage = mock_usage
    mock_litellm_responses.return_value = mock_response

    from openhands.sdk.llm.message import TextContent

    llm = LLM(model="o1-preview")
    messages = [
        Message(role="user", content=[TextContent(text="Hello")]),
        Message(role="assistant", content=[TextContent(text="Hi there!")]),
    ]

    with patch.object(llm, "_telemetry") as mock_telemetry:
        mock_telemetry.log_enabled = False
        llm.responses(messages=messages)

    # Verify litellm.responses was called
    mock_litellm_responses.assert_called_once()
    call_args = mock_litellm_responses.call_args

    # The input should be converted from Message objects
    expected_input = "User: Hello\n\nAssistant: Hi there!"
    assert call_args[1]["input"] == expected_input


@patch("openhands.sdk.llm.llm.litellm_responses")
def test_responses_method_with_string_messages(mock_litellm_responses):
    """Test responses method when messages parameter is a string."""
    # Mock the litellm response
    mock_response = Mock()
    mock_response.id = "resp_string"
    mock_response.model = "o1-preview"
    mock_response.created = 1234567893
    mock_response.output = []
    # Add usage mock
    mock_usage = Mock()
    mock_usage.input_tokens = 8
    mock_usage.output_tokens = 12
    mock_usage.total_tokens = 20
    mock_response.usage = mock_usage
    mock_litellm_responses.return_value = mock_response

    llm = LLM(model="o1-preview")

    with patch.object(llm, "_telemetry") as mock_telemetry:
        mock_telemetry.log_enabled = False
        llm.responses(messages="Direct string input")

    # Verify litellm.responses was called with the string directly
    mock_litellm_responses.assert_called_once()
    call_args = mock_litellm_responses.call_args
    assert call_args[1]["input"] == "Direct string input"


def test_responses_method_input_takes_precedence():
    """Test that input parameter takes precedence over messages."""
    llm = LLM(model="o1-preview")
    messages = [{"role": "user", "content": "This should be ignored"}]

    with patch("openhands.sdk.llm.llm.litellm_responses") as mock_litellm_responses:
        mock_response = Mock()
        mock_response.id = "resp_precedence"
        mock_response.model = "o1-preview"
        mock_response.created = 1234567894
        mock_response.output = []
        # Add usage mock
        mock_usage = Mock()
        mock_usage.input_tokens = 5
        mock_usage.output_tokens = 10
        mock_usage.total_tokens = 15
        mock_response.usage = mock_usage
        mock_litellm_responses.return_value = mock_response

        with patch.object(llm, "_telemetry") as mock_telemetry:
            mock_telemetry.log_enabled = False
            llm.responses(messages=messages, input="Direct input wins")

    # Verify the direct input was used, not the converted messages
    call_args = mock_litellm_responses.call_args
    assert call_args[1]["input"] == "Direct input wins"


@patch("openhands.sdk.llm.llm.litellm_responses")
def test_responses_method_parameter_normalization(mock_litellm_responses):
    """Test that parameters are properly normalized for Responses API."""
    # Mock the litellm response
    mock_response = Mock()
    mock_response.id = "resp_normalization"
    mock_response.model = "o1-preview"
    mock_response.created = 1234567895
    mock_response.output = []
    # Add usage mock
    mock_usage = Mock()
    mock_usage.input_tokens = 20
    mock_usage.output_tokens = 30
    mock_usage.total_tokens = 50
    mock_response.usage = mock_usage
    mock_litellm_responses.return_value = mock_response

    llm = LLM(
        model="o1-preview",
        temperature=0.7,
        max_output_tokens=1000,
        reasoning_effort="medium",
    )

    with patch.object(llm, "_telemetry") as mock_telemetry:
        mock_telemetry.log_enabled = False
        llm.responses(
            input="Test input",
            tools=[
                {"type": "function", "function": {"name": "test"}}
            ],  # Should be removed
            stop=["STOP"],  # Should be removed
        )

    # Verify parameters were normalized
    call_args = mock_litellm_responses.call_args
    kwargs = call_args[1]

    # Should have reasoning_effort for o1 models
    assert "reasoning_effort" in kwargs
    assert kwargs["reasoning_effort"] == "medium"

    # Should have max_output_tokens
    assert "max_output_tokens" in kwargs
    assert kwargs["max_output_tokens"] == 1000

    # Should NOT have tools or stop (not supported by Responses API)
    assert "tools" not in kwargs
    assert "stop" not in kwargs

    # Temperature should be removed for reasoning models
    assert "temperature" not in kwargs
