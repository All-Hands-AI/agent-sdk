"""Tests for LLM Responses API functionality."""

from unittest.mock import Mock, patch

import pytest

from openhands.sdk.llm.llm import LLM
from openhands.sdk.llm.message import Message


def test_responses_api_support_and_error():
    """Support flag should align with error behavior for unsupported models."""
    # Test with a model that supports Responses API
    llm = LLM(model="o1-preview")
    assert llm.is_responses_api_supported()

    # Unsupported: flag false and calling responses() raises
    llm = LLM(model="gpt-3.5-turbo")
    assert not llm.is_responses_api_supported()
    with pytest.raises(ValueError, match="does not support the Responses API"):
        llm.responses(input="Hello")


def _removed_duplicate_responses_method_unsupported_model():
    """Deprecated duplicate: covered by test_responses_api_support_and_error."""
    pass


def test_responses_method_streaming_not_supported():
    """Test that responses method raises error when streaming is requested."""
    llm = LLM(model="o1-preview")

    with pytest.raises(ValueError, match="Streaming is not supported"):
        llm.responses(input="Hello", stream=True)


def test_responses_method_no_input():
    """Test that responses method raises error when no input is provided."""
    llm = LLM(model="o1-preview")

    with pytest.raises(ValueError, match="Either messages or input must be provided"):
        llm.responses()


@patch("openhands.sdk.llm.llm.litellm_responses")
def test_responses_method_with_input_string(mock_litellm_responses):
    """Test responses method with direct input string."""
    # Mock the litellm response
    mock_response = Mock()
    mock_response.id = "resp_123"
    mock_response.model = "o1-preview"
    mock_response.created_at = 1234567890
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

    # Verify litellm.responses was called correctly; store defaults to True
    mock_litellm_responses.assert_called_once()
    call_args = mock_litellm_responses.call_args
    assert call_args[1]["input"] == "Hello, how are you?"
    assert call_args[1]["model"] == "o1-preview"
    assert call_args[1].get("store", False) is True

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
    mock_response.created_at = 1234567891
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

    # The input should be a structured list of message items for Responses API
    assert isinstance(call_args[1]["input"], list)
    assert call_args[1]["input"] == [
        {"role": "user", "content": "What is 2+2?"},
        {"role": "assistant", "content": "2+2 equals 4."},
    ]

    # Verify the call was made correctly


@patch("openhands.sdk.llm.llm.litellm_responses")
def test_responses_method_with_message_objects(mock_litellm_responses):
    """Test responses method with Message objects."""
    # Mock the litellm response
    mock_response = Mock()
    mock_response.id = "resp_789"
    mock_response.model = "o1-preview"
    mock_response.created_at = 1234567892
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

    # The input should be a structured list when Message objects are provided
    assert isinstance(call_args[1]["input"], list)
    assert call_args[1]["input"] == [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
    ]


@patch("openhands.sdk.llm.llm.litellm_responses")
def test_responses_method_with_string_messages(mock_litellm_responses):
    """Test responses method when messages parameter is a string."""
    # Mock the litellm response
    mock_response = Mock()
    mock_response.id = "resp_string"
    mock_response.model = "o1-preview"
    mock_response.created_at = 1234567893
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
        mock_response.created_at = 1234567894
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
    mock_response.created_at = 1234567895
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

        from openhands.sdk.tool.schema import ActionBase
        from openhands.sdk.tool.tool import Tool

        class _Args(ActionBase):
            pass

        tool = Tool(name="test", description="desc", action_type=_Args)

        llm.responses(
            input="Test input",
            tools=[tool],
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

    # Should have tools (supported by Responses API) but NOT stop (not supported)
    assert "tools" in kwargs
    # Responses API expects flattened tool dicts with function name; don't over-specify
    assert isinstance(kwargs["tools"], list) and len(kwargs["tools"]) == 1
    assert kwargs["tools"][0]["type"] == "function"
    assert kwargs["tools"][0]["name"] == "test"
    assert "stop" not in kwargs

    # Temperature should be removed for reasoning models
    assert "temperature" not in kwargs


@patch("openhands.sdk.llm.llm.litellm_responses")
def test_responses_method_parameter_normalization_with_tool_object(
    mock_litellm_responses,
):
    """Tools provided as our Tool objects should be converted via
    to_responses_tool()."""
    mock_response = Mock()
    mock_response.id = "resp_toolobj"
    mock_response.model = "o1-preview"
    mock_response.created_at = 1234567896
    mock_response.output = []
    mock_usage = Mock()
    mock_usage.input_tokens = 7
    mock_usage.output_tokens = 11
    mock_usage.total_tokens = 18
    mock_response.usage = mock_usage
    mock_litellm_responses.return_value = mock_response

    from pydantic import Field

    from openhands.sdk.tool.schema import ActionBase
    from openhands.sdk.tool.tool import Tool

    class MyArgs(ActionBase):
        x: int = Field(..., description="x value")

    t = Tool(name="my_tool", description="runs", action_type=MyArgs)

    llm = LLM(model="o1-preview", reasoning_effort="high", max_output_tokens=123)

    with patch.object(llm, "_telemetry") as mock_telemetry:
        mock_telemetry.log_enabled = False
        llm.responses(input="run", tools=[t])

    call_args = mock_litellm_responses.call_args
    kwargs = call_args[1]

    tool = kwargs["tools"][0]
    assert tool["type"] == "function"
    assert tool["name"] == "my_tool"
    assert tool["description"] == "runs"
    params = tool["parameters"]
    assert params["type"] == "object"
    props = params["properties"]
    assert "x" in props
    assert props["x"]["type"] == "integer"
    assert props["x"]["description"] == "x value"
    # schema may include additional properties (e.g., security_risk); don't over-specify
    assert "x" in params["required"]
    assert "stop" not in kwargs
    assert kwargs["max_output_tokens"] == 123
