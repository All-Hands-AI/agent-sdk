"""Tests for LLM completion functionality, configuration, and metrics tracking."""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from openhands.core.config import LLMConfig
from openhands.core.llm import LLM


def create_mock_response(content: str = "Test response", response_id: str = "test-id"):
    """Helper function to create properly structured mock responses."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = content

    # Create usage mock
    mock_usage = MagicMock()
    mock_usage.get.side_effect = lambda key, default=None: {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "model_extra": {},
    }.get(key, default)
    mock_usage.prompt_tokens_details = None

    # Response data mapping
    response_data = {
        "choices": mock_response.choices,
        "usage": mock_usage,
        "id": response_id,
    }

    # Mock both .get() and dict-like access (LLM code uses both patterns inconsistently)
    mock_response.get.side_effect = lambda key, default=None: response_data.get(
        key, default
    )
    mock_response.__getitem__ = lambda self, key: response_data[key]

    return mock_response


@pytest.fixture
def default_config():
    return LLMConfig(
        model="gpt-4o",
        api_key=SecretStr("test_key"),
        num_retries=2,
        retry_min_wait=1,
        retry_max_wait=2,
    )


@patch("openhands.core.llm.llm.litellm_completion")
def test_llm_completion_basic(mock_completion, default_config):
    """Test basic LLM completion functionality."""
    mock_response = create_mock_response("Test response")
    mock_completion.return_value = mock_response

    llm = LLM(config=default_config)

    # Test completion
    messages = [{"role": "user", "content": "Hello"}]
    response = llm.completion(messages=messages)

    assert response == mock_response
    mock_completion.assert_called_once()


def test_llm_streaming_not_supported(default_config):
    """Test that streaming is not supported in the basic LLM class."""
    llm = LLM(config=default_config)

    messages = [{"role": "user", "content": "Hello"}]

    # Streaming should raise an error
    with pytest.raises(ValueError, match="Streaming is not supported"):
        llm.completion(messages=messages, stream=True)


@patch("openhands.core.llm.llm.litellm_completion")
def test_llm_completion_with_tools(mock_completion, default_config):
    """Test LLM completion with tools."""
    mock_response = create_mock_response("I'll use the tool")
    mock_response.choices[0].message.tool_calls = [
        MagicMock(
            id="call_123",
            type="function",
            function=MagicMock(name="test_tool", arguments='{"param": "value"}'),
        )
    ]
    mock_completion.return_value = mock_response

    llm = LLM(config=default_config)

    # Test completion with tools
    messages = [{"role": "user", "content": "Use the test tool"}]
    tools = [
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


@patch("openhands.core.llm.llm.litellm_completion")
def test_llm_completion_error_handling(mock_completion, default_config):
    """Test LLM completion error handling."""
    # Mock an exception
    mock_completion.side_effect = Exception("Test error")

    llm = LLM(config=default_config)

    messages = [{"role": "user", "content": "Hello"}]

    # Should propagate the exception
    with pytest.raises(Exception, match="Test error"):
        llm.completion(messages=messages)


def test_llm_token_counting_basic(default_config):
    """Test basic token counting functionality."""
    llm = LLM(config=default_config)

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
    llm = LLM(config=default_config)

    # Model info initialization should complete without errors
    llm.init_model_info()

    # Model info might be None for unknown models, which is fine
    assert llm.model_info is None or isinstance(llm.model_info, dict)


def test_llm_feature_detection(default_config):
    """Test various feature detection methods."""
    llm = LLM(config=default_config)

    # All feature detection methods should return booleans
    assert isinstance(llm.vision_is_active(), bool)
    assert isinstance(llm.is_function_calling_active(), bool)
    assert isinstance(llm.is_caching_prompt_active(), bool)


def test_llm_cost_tracking(default_config):
    """Test cost tracking functionality."""
    llm = LLM(config=default_config)

    initial_cost = llm.metrics.accumulated_cost

    # Add some cost
    llm.metrics.add_cost(1.5)

    assert llm.metrics.accumulated_cost == initial_cost + 1.5
    assert len(llm.metrics.costs) >= 1


def test_llm_latency_tracking(default_config):
    """Test latency tracking functionality."""
    llm = LLM(config=default_config)

    initial_count = len(llm.metrics.response_latencies)

    # Add some latency
    llm.metrics.add_response_latency(0.5, "test-response")

    assert len(llm.metrics.response_latencies) == initial_count + 1
    assert llm.metrics.response_latencies[-1].latency == 0.5


def test_llm_token_usage_tracking(default_config):
    """Test token usage tracking functionality."""
    llm = LLM(config=default_config)

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


@patch("openhands.core.llm.llm.litellm_completion")
def test_llm_completion_with_custom_params(mock_completion, default_config):
    """Test LLM completion with custom parameters."""
    mock_response = create_mock_response("Custom response")
    mock_completion.return_value = mock_response

    # Create config with custom parameters
    custom_config = LLMConfig(
        model="gpt-4o",
        api_key=SecretStr("test_key"),
        temperature=0.8,
        max_output_tokens=500,
        top_p=0.9,
    )

    llm = LLM(config=custom_config)

    messages = [{"role": "user", "content": "Hello with custom params"}]
    response = llm.completion(messages=messages)

    assert response == mock_response
    mock_completion.assert_called_once()

    # Verify that custom parameters were used in the call
    call_kwargs = mock_completion.call_args[1]
    assert call_kwargs.get("temperature") == 0.8
    assert call_kwargs.get("max_completion_tokens") == 500
    assert call_kwargs.get("top_p") == 0.9


# This file focuses on LLM completion functionality, configuration options,
# and metrics tracking for the synchronous LLM implementation
