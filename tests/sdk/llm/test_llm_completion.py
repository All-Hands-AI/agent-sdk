"""Tests for LLM completion functionality, configuration, and metrics tracking."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from litellm.types.utils import Choices, Message, ModelResponse, Usage
from pydantic import SecretStr

from openhands.sdk.llm import LLM


def create_mock_response(content: str = "Test response", response_id: str = "test-id"):
    """Helper function to create properly structured mock responses."""
    return ModelResponse(
        id=response_id,
        choices=[
            Choices(
                finish_reason="stop",
                index=0,
                message=Message(
                    content=content,
                    role="assistant",
                ),
            )
        ],
        created=1234567890,
        model="gpt-4o",
        object="chat.completion",
        system_fingerprint="test",
        usage=Usage(
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
        ),
    )


@pytest.fixture
def default_config():
    return LLM(
        model="gpt-4o",
        api_key=SecretStr("test_key"),
        num_retries=2,
        retry_min_wait=1,
        retry_max_wait=2,
    )


@patch("openhands.sdk.llm.llm.litellm_completion")
def test_llm_completion_basic(mock_completion):
    """Test basic LLM completion functionality."""
    mock_response = create_mock_response("Test response")
    mock_completion.return_value = mock_response

    # Create LLM after the patch is applied
    llm = LLM(
        model="gpt-4o",
        api_key=SecretStr("test_key"),
        num_retries=2,
        retry_min_wait=1,
        retry_max_wait=2,
    )

    # Test completion
    messages = [{"role": "user", "content": "Hello"}]
    response = llm.completion(messages=messages)

    assert response == mock_response
    mock_completion.assert_called_once()


def test_llm_streaming_not_supported(default_config):
    """Test that streaming is not supported in the basic LLM class."""
    llm = default_config

    messages = [{"role": "user", "content": "Hello"}]

    # Streaming should raise an error
    with pytest.raises(ValueError, match="Streaming is not supported"):
        llm.completion(messages=messages, stream=True)


@patch("openhands.sdk.llm.llm.litellm_completion")
def test_llm_completion_with_tools(mock_completion):
    """Test LLM completion with tools."""
    mock_response = create_mock_response("I'll use the tool")
    mock_response.choices[0].message.tool_calls = [  # type: ignore
        MagicMock(
            id="call_123",
            type="function",
            function=MagicMock(name="test_tool", arguments='{"param": "value"}'),
        )
    ]
    mock_completion.return_value = mock_response

    # Create LLM after the patch is applied
    llm = LLM(
        model="gpt-4o",
        api_key=SecretStr("test_key"),
        num_retries=2,
        retry_min_wait=1,
        retry_max_wait=2,
    )

    # Test completion with tools
    messages = [{"role": "user", "content": "Use the test tool"}]
    tools: list[Any] = [
        {
            "type": "function",
            "function": {
                "name": "test_tool",
                "description": "A test tool",
                "parameters": {
                    "type": "object",
                    "properties": {"param": {"type": "string"}},
                },
            },
        }
    ]

    response = llm.completion(messages=messages, tools=tools)

    assert response == mock_response
    mock_completion.assert_called_once()


@patch("openhands.sdk.llm.llm.litellm_completion")
def test_llm_completion_error_handling(mock_completion):
    """Test LLM completion error handling."""
    # Mock an exception
    mock_completion.side_effect = Exception("Test error")

    # Create LLM after the patch is applied
    llm = LLM(
        model="gpt-4o",
        api_key=SecretStr("test_key"),
        num_retries=2,
        retry_min_wait=1,
        retry_max_wait=2,
    )

    messages = [{"role": "user", "content": "Hello"}]

    # Should propagate the exception
    with pytest.raises(Exception, match="Test error"):
        llm.completion(messages=messages)


def test_llm_token_counting_basic(default_config):
    """Test basic token counting functionality."""
    llm = default_config

    # Test with simple messages
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
    ]

    # Token counting should return a non-negative integer
    token_count = llm.get_token_count(messages)
    assert isinstance(token_count, int)
    assert token_count >= 0


def test_llm_model_info_initialization(default_config):
    """Test model info initialization."""
    llm = default_config

    # Model info initialization should complete without errors
    llm._init_model_info_and_caps()

    # Model info might be None for unknown models, which is fine
    assert llm.model_info is None or isinstance(llm.model_info, dict)


def test_llm_feature_detection(default_config):
    """Test various feature detection methods."""
    llm = default_config

    # All feature detection methods should return booleans
    assert isinstance(llm.vision_is_active(), bool)
    assert isinstance(llm.is_function_calling_active(), bool)
    assert isinstance(llm.is_caching_prompt_active(), bool)


def test_llm_cost_tracking(default_config):
    """Test cost tracking functionality."""
    llm = default_config

    initial_cost = llm.metrics.accumulated_cost

    # Add some cost
    llm.metrics.add_cost(1.5)

    assert llm.metrics.accumulated_cost == initial_cost + 1.5
    assert len(llm.metrics.costs) >= 1


def test_llm_latency_tracking(default_config):
    """Test latency tracking functionality."""
    llm = default_config

    initial_count = len(llm.metrics.response_latencies)

    # Add some latency
    llm.metrics.add_response_latency(0.5, "test-response")

    assert len(llm.metrics.response_latencies) == initial_count + 1
    assert llm.metrics.response_latencies[-1].latency == 0.5


def test_llm_token_usage_tracking(default_config):
    """Test token usage tracking functionality."""
    llm = default_config

    initial_count = len(llm.metrics.token_usages)

    # Add some token usage
    llm.metrics.add_token_usage(
        prompt_tokens=10,
        completion_tokens=5,
        cache_read_tokens=2,
        cache_write_tokens=1,
        context_window=4096,
        response_id="test-response",
    )

    assert len(llm.metrics.token_usages) == initial_count + 1

    # Check accumulated token usage
    accumulated = llm.metrics.accumulated_token_usage
    assert accumulated.prompt_tokens >= 10
    assert accumulated.completion_tokens >= 5


@patch("openhands.sdk.llm.llm.litellm_completion")
def test_llm_completion_with_custom_params(mock_completion, default_config):
    """Test LLM completion with custom parameters."""
    mock_response = create_mock_response("Custom response")
    mock_completion.return_value = mock_response

    # Create config with custom parameters
    custom_config = LLM(
        model="gpt-4o",
        api_key=SecretStr("test_key"),
        temperature=0.8,
        max_output_tokens=500,
        top_p=0.9,
    )

    llm = custom_config

    messages = [{"role": "user", "content": "Hello with custom params"}]
    response = llm.completion(messages=messages)

    assert response == mock_response
    mock_completion.assert_called_once()

    # Verify that custom parameters were used in the call
    call_kwargs = mock_completion.call_args[1]
    assert call_kwargs.get("temperature") == 0.8
    assert call_kwargs.get("max_completion_tokens") == 500
    assert call_kwargs.get("top_p") == 0.9


@patch("openhands.sdk.llm.llm.litellm_completion")
def test_llm_completion_non_function_call_mode(mock_completion):
    """Test LLM completion with non-function call mode (prompt-based tool calling)."""
    # Create a mock response that looks like a non-function call response
    # but contains tool usage in text format
    mock_response = create_mock_response(
        "I'll help you with that. Let me use the test tool.\n\n"
        "<function_calls>\n"
        '<invoke name="test_tool">\n'
        '<parameter name="param">test_value</parameter>\n'
        "</invoke>\n"
        "</function_calls>"
    )
    mock_completion.return_value = mock_response

    # Create LLM with native_tool_calling explicitly set to False
    # This forces the LLM to use prompt-based tool calling instead of native FC
    llm = LLM(
        model="gpt-4o",
        api_key=SecretStr("test_key"),
        native_tool_calling=False,  # This is the key setting for non-function call mode
        num_retries=2,
        retry_min_wait=1,
        retry_max_wait=2,
    )

    # Verify that function calling is not active
    assert not llm.is_function_calling_active()

    # Test completion with tools - this should trigger the non-function call path
    messages = [
        {"role": "user", "content": "Use the test tool with param 'test_value'"}
    ]
    tools: list[Any] = [
        {
            "type": "function",
            "function": {
                "name": "test_tool",
                "description": "A test tool for non-function call mode",
                "parameters": {
                    "type": "object",
                    "properties": {"param": {"type": "string"}},
                    "required": ["param"],
                },
            },
        }
    ]

    # Verify that tools should be mocked (non-function call path)
    assert llm.should_mock_tool_calls(tools)

    # Call completion - this should go through the prompt-based tool calling path
    response = llm.completion(messages=messages, tools=tools)

    # Verify the response
    assert response is not None
    mock_completion.assert_called_once()

    # Verify that the call was made without native tools parameter
    # (since we're using prompt-based tool calling)
    call_kwargs = mock_completion.call_args[1]
    # In non-function call mode, tools should not be passed to the underlying LLM
    assert call_kwargs.get("tools") is None or call_kwargs.get("tools") == []

    # Verify that the messages were modified for prompt-based tool calling
    call_messages = mock_completion.call_args[1]["messages"]
    # The messages should be different from the original due to prompt modification
    assert len(call_messages) >= len(messages)


@patch("openhands.sdk.llm.llm.litellm_completion")
def test_llm_completion_non_function_call_mode_without_tools(mock_completion):
    """Test LLM completion with non-function call mode but no tools provided."""
    mock_response = create_mock_response("This is a regular response without tools.")
    mock_completion.return_value = mock_response

    # Create LLM with native_tool_calling explicitly set to False
    llm = LLM(
        model="gpt-4o",
        api_key=SecretStr("test_key"),
        native_tool_calling=False,
        num_retries=2,
        retry_min_wait=1,
        retry_max_wait=2,
    )

    # Verify that function calling is not active
    assert not llm.is_function_calling_active()

    # Test completion without tools
    messages = [{"role": "user", "content": "Hello, how are you?"}]

    # Verify that no tools should be mocked when no tools are provided
    assert not llm.should_mock_tool_calls(None)
    assert not llm.should_mock_tool_calls([])

    # Call completion - this should go through the regular path
    response = llm.completion(messages=messages)

    # Verify the response
    assert response == mock_response
    mock_completion.assert_called_once()

    # Verify that the call was made normally
    call_kwargs = mock_completion.call_args[1]
    assert call_kwargs.get("tools") is None

    # Verify that the messages were not modified
    call_messages = mock_completion.call_args[1]["messages"]
    assert call_messages == messages


@patch("openhands.sdk.llm.llm.litellm_completion")
def test_llm_completion_function_call_vs_non_function_call_mode(mock_completion):
    """Test the difference between function call mode and non-function call mode."""
    mock_response = create_mock_response("Test response")
    mock_completion.return_value = mock_response

    tools: list[Any] = [
        {
            "type": "function",
            "function": {
                "name": "test_tool",
                "description": "A test tool",
                "parameters": {
                    "type": "object",
                    "properties": {"param": {"type": "string"}},
                },
            },
        }
    ]
    messages = [{"role": "user", "content": "Use the test tool"}]

    # Test with native function calling enabled (default behavior for gpt-4o)
    llm_native = LLM(
        model="gpt-4o",
        # Most of the time, we put in SecretStr("
        # but the validation should also handle plain str for convenience as well
        api_key="test_key",  # type: ignore
        native_tool_calling=True,  # Explicitly enable native function calling
        num_retries=2,
        retry_min_wait=1,
        retry_max_wait=2,
    )

    # Verify function calling is active
    assert llm_native.is_function_calling_active()
    # Should not mock tools when native function calling is active
    assert not llm_native.should_mock_tool_calls(tools)

    # Test with native function calling disabled
    llm_non_native = LLM(
        model="gpt-4o",
        api_key=SecretStr("test_key"),
        native_tool_calling=False,  # Explicitly disable native function calling
        num_retries=2,
        retry_min_wait=1,
        retry_max_wait=2,
    )

    # Verify function calling is not active
    assert not llm_non_native.is_function_calling_active()
    # Should mock tools when native function calling is disabled but tools are provided
    assert llm_non_native.should_mock_tool_calls(tools)

    # Call both and verify different behavior
    mock_completion.reset_mock()
    response_native = llm_native.completion(messages=messages, tools=tools)
    native_call_kwargs = mock_completion.call_args[1]

    mock_completion.reset_mock()
    response_non_native = llm_non_native.completion(messages=messages, tools=tools)
    non_native_call_kwargs = mock_completion.call_args[1]

    # Both should return responses
    assert response_native == mock_response
    assert response_non_native == mock_response

    # But the underlying calls should be different:
    # Native mode should pass tools to the LLM
    assert native_call_kwargs.get("tools") == tools

    # Non-native mode should not pass tools (they're handled via prompts)
    assert (
        non_native_call_kwargs.get("tools") is None
        or non_native_call_kwargs.get("tools") == []
    )


# This file focuses on LLM completion functionality, configuration options,
# and metrics tracking for the synchronous LLM implementation
