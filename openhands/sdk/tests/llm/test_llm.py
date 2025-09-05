from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from litellm.exceptions import (
    RateLimitError,
)
from pydantic import SecretStr

from openhands.sdk.llm import LLM, Message, TextContent
from openhands.sdk.llm.exceptions import LLMNoResponseError
from openhands.sdk.llm.utils.metrics import Metrics, TokenUsage


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


@pytest.fixture(autouse=True)
def mock_logger(monkeypatch):
    # suppress logging of completion data to file
    mock_logger = MagicMock()
    monkeypatch.setattr("openhands.sdk.llm.llm.logger", mock_logger)
    return mock_logger


@pytest.fixture
def default_config() -> dict[str, Any]:
    return {
        "model": "gpt-4o",
        "api_key": SecretStr("test_key"),
        "num_retries": 2,
        "retry_min_wait": 1,
        "retry_max_wait": 2,
    }


def test_llm_init_with_default_config(default_config):
    llm = LLM(**default_config, service_id="test-service")
    assert llm.model == "gpt-4o"
    assert llm.api_key is not None and llm.api_key.get_secret_value() == "test_key"
    assert isinstance(llm.metrics, Metrics)
    assert llm.metrics.model_name == "gpt-4o"


def test_token_usage_add():
    """Test that TokenUsage instances can be added together."""
    # Create two TokenUsage instances
    usage1 = TokenUsage(
        model="model1",
        prompt_tokens=10,
        completion_tokens=5,
        cache_read_tokens=3,
        cache_write_tokens=2,
        response_id="response-1",
    )

    usage2 = TokenUsage(
        model="model2",
        prompt_tokens=8,
        completion_tokens=6,
        cache_read_tokens=2,
        cache_write_tokens=4,
        response_id="response-2",
    )

    # Add them together
    combined = usage1 + usage2

    # Verify the result
    assert combined.model == "model1"  # Should keep the model from the first instance
    assert combined.prompt_tokens == 18  # 10 + 8
    assert combined.completion_tokens == 11  # 5 + 6
    assert combined.cache_read_tokens == 5  # 3 + 2
    assert combined.cache_write_tokens == 6  # 2 + 4
    assert (
        combined.response_id == "response-1"
    )  # Should keep the response_id from the first instance


def test_metrics_merge_accumulated_token_usage():
    """Test that accumulated token usage is properly merged between two Metrics
    instances."""
    # Create two Metrics instances
    metrics1 = Metrics(model_name="model1")
    metrics2 = Metrics(model_name="model2")

    # Add token usage to each
    metrics1.add_token_usage(10, 5, 3, 2, 1000, "response-1")
    metrics2.add_token_usage(8, 6, 2, 4, 1000, "response-2")

    # Verify initial accumulated token usage
    metrics1_data = metrics1.get()
    accumulated1 = metrics1_data["accumulated_token_usage"]
    assert accumulated1["prompt_tokens"] == 10
    assert accumulated1["completion_tokens"] == 5
    assert accumulated1["cache_read_tokens"] == 3
    assert accumulated1["cache_write_tokens"] == 2

    metrics2_data = metrics2.get()
    accumulated2 = metrics2_data["accumulated_token_usage"]
    assert accumulated2["prompt_tokens"] == 8
    assert accumulated2["completion_tokens"] == 6
    assert accumulated2["cache_read_tokens"] == 2
    assert accumulated2["cache_write_tokens"] == 4

    # Merge metrics2 into metrics1
    metrics1.merge(metrics2)

    # Verify merged accumulated token usage
    merged_data = metrics1.get()
    merged_accumulated = merged_data["accumulated_token_usage"]
    assert merged_accumulated["prompt_tokens"] == 18  # 10 + 8
    assert merged_accumulated["completion_tokens"] == 11  # 5 + 6
    assert merged_accumulated["cache_read_tokens"] == 5  # 3 + 2
    assert merged_accumulated["cache_write_tokens"] == 6  # 2 + 4


def test_metrics_diff():
    """Test that metrics diff correctly calculates the difference between two
    metrics."""
    # Create baseline metrics
    baseline = Metrics(model_name="test-model")
    baseline.add_cost(1.0)
    baseline.add_token_usage(10, 5, 2, 1, 1000, "baseline-response")
    baseline.add_response_latency(0.5, "baseline-response")

    # Create current metrics with additional data
    current = Metrics(model_name="test-model")
    current.merge(baseline)  # Start with baseline
    current.add_cost(2.0)  # Add more cost
    current.add_token_usage(15, 8, 3, 2, 1000, "current-response")  # Add more tokens
    current.add_response_latency(0.8, "current-response")  # Add more latency

    # Calculate diff
    diff = current.diff(baseline)

    # Verify diff contains only the additional data
    diff_data = diff.get()
    assert diff_data["accumulated_cost"] == 2.0  # Only the additional cost
    assert len(diff_data["costs"]) == 1  # Only the additional cost entry
    assert len(diff_data["token_usages"]) == 1  # Only the additional token usage
    assert len(diff_data["response_latencies"]) == 1  # Only the additional latency

    # Verify accumulated token usage diff
    accumulated_diff = diff_data["accumulated_token_usage"]
    assert accumulated_diff["prompt_tokens"] == 15  # Only the additional tokens
    assert accumulated_diff["completion_tokens"] == 8
    assert accumulated_diff["cache_read_tokens"] == 3
    assert accumulated_diff["cache_write_tokens"] == 2


@patch("openhands.sdk.llm.llm.litellm_completion")
def test_llm_completion_with_mock(mock_completion, default_config):
    """Test LLM completion with mocked litellm."""
    mock_response = create_mock_response("Test response")
    mock_completion.return_value = mock_response

    llm = LLM(**default_config)  # type: ignore

    # Test completion
    messages = [{"role": "user", "content": "Hello"}]
    response = llm.completion(messages=messages)

    assert response == mock_response
    mock_completion.assert_called_once()


@patch("openhands.sdk.llm.llm.litellm_completion")
def test_llm_retry_on_rate_limit(mock_completion, default_config):
    """Test that LLM retries on rate limit errors."""
    mock_response = create_mock_response("Success after retry")

    mock_completion.side_effect = [
        RateLimitError(
            message="Rate limit exceeded",
            llm_provider="test_provider",
            model="test_model",
        ),
        mock_response,
    ]

    llm = LLM(**default_config)  # type: ignore

    # Test completion with retry
    messages = [{"role": "user", "content": "Hello"}]
    response = llm.completion(messages=messages)

    assert response == mock_response
    assert mock_completion.call_count == 2  # First call failed, second succeeded


def test_llm_cost_calculation(default_config):
    """Test LLM cost calculation and metrics tracking."""
    llm = LLM(**default_config)  # type: ignore

    # Test cost addition
    assert llm.metrics is not None
    initial_cost = llm.metrics.accumulated_cost
    llm.metrics.add_cost(1.5)
    assert llm.metrics.accumulated_cost == initial_cost + 1.5

    # Test cost validation
    with pytest.raises(ValueError, match="Added cost cannot be negative"):
        llm.metrics.add_cost(-1.0)


def test_llm_token_counting(default_config):
    """Test LLM token counting functionality."""
    llm = LLM(**default_config)  # type: ignore

    # Test with dict messages
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
    ]

    # Token counting might return 0 if model not supported, but should not error
    token_count = llm.get_token_count(messages)
    assert isinstance(token_count, int)
    assert token_count >= 0


def test_llm_vision_support(default_config):
    """Test LLM vision support detection."""
    llm = LLM(**default_config)  # type: ignore

    # Vision support detection should work without errors
    vision_active = llm.vision_is_active()
    assert isinstance(vision_active, bool)


def test_llm_function_calling_support(default_config):
    """Test LLM function calling support detection."""
    llm = LLM(**default_config)  # type: ignore

    # Function calling support detection should work without errors
    function_calling_active = llm.is_function_calling_active()
    assert isinstance(function_calling_active, bool)


def test_llm_caching_support(default_config):
    """Test LLM prompt caching support detection."""
    llm = LLM(**default_config)  # type: ignore

    # Caching support detection should work without errors
    caching_active = llm.is_caching_prompt_active()
    assert isinstance(caching_active, bool)


def test_llm_string_representation(default_config):
    """Test LLM string representation."""
    llm = LLM(**default_config)  # type: ignore

    str_repr = str(llm)
    assert "LLM(" in str_repr
    assert "gpt-4o" in str_repr

    repr_str = repr(llm)
    assert repr_str == str_repr


def test_llm_openhands_provider_rewrite():
    """Test OpenHands provider rewriting."""
    llm = LLM(model="openhands/gpt-4o")

    # Model should be rewritten to litellm_proxy format
    assert llm.model == "litellm_proxy/gpt-4o"
    assert llm.base_url == "https://llm-proxy.app.all-hands.dev/"


def test_llm_message_formatting(default_config):
    """Test LLM message formatting for different message types."""
    llm = LLM(**default_config)  # type: ignore

    # Test with single Message object
    message = Message(role="user", content=[TextContent(text="Hello")])
    formatted = llm.format_messages_for_llm([message])
    assert isinstance(formatted, list)
    assert len(formatted) == 1
    assert isinstance(formatted[0], dict)

    # Test with list of Message objects
    messages = [
        Message(role="user", content=[TextContent(text="Hello")]),
        Message(role="assistant", content=[TextContent(text="Hi there!")]),
    ]
    formatted = llm.format_messages_for_llm(messages)
    assert isinstance(formatted, list)
    assert len(formatted) == 2
    assert all(isinstance(msg, dict) for msg in formatted)


def test_metrics_copy():
    """Test that metrics can be copied correctly."""
    original = Metrics(model_name="test-model")
    original.add_cost(1.0)
    original.add_token_usage(10, 5, 2, 1, 1000, "test-response")
    original.add_response_latency(0.5, "test-response")

    # Create a copy
    copied = original.copy()

    # Verify copy has same data
    original_data = original.get()
    copied_data = copied.get()

    assert original_data["accumulated_cost"] == copied_data["accumulated_cost"]
    assert len(original_data["costs"]) == len(copied_data["costs"])
    assert len(original_data["token_usages"]) == len(copied_data["token_usages"])
    assert len(original_data["response_latencies"]) == len(
        copied_data["response_latencies"]
    )

    # Verify they are independent (modifying one doesn't affect the other)
    copied.add_cost(2.0)
    assert original.accumulated_cost != copied.accumulated_cost


def test_metrics_log():
    """Test metrics logging functionality."""
    metrics = Metrics(model_name="test-model")
    metrics.add_cost(1.5)
    metrics.add_token_usage(10, 5, 2, 1, 1000, "test-response")

    log_output = metrics.log()
    assert isinstance(log_output, str)
    assert "accumulated_cost" in log_output
    assert "1.5" in log_output


def test_llm_config_validation():
    """Test LLM configuration validation."""
    # Test with minimal valid config
    llm = LLM(model="gpt-4o")
    assert llm.model == "gpt-4o"

    # Test with full config
    full_llm = LLM(
        model="gpt-4o",
        api_key=SecretStr("test_key"),
        base_url="https://api.openai.com/v1",
        temperature=0.7,
        max_output_tokens=1000,
        num_retries=3,
        retry_min_wait=1,
        retry_max_wait=10,
    )
    assert full_llm.temperature == 0.7
    assert full_llm.max_output_tokens == 1000


@patch("openhands.sdk.llm.llm.litellm_completion")
def test_llm_no_response_error(mock_completion):
    """Test handling of LLMNoResponseError."""
    # Mock empty response
    mock_response = MagicMock()
    mock_response.choices = []
    mock_response.get.return_value = None
    mock_response.__getitem__.side_effect = lambda key: {
        "choices": [],
        "usage": None,
        "id": None,
    }[key]
    mock_completion.return_value = mock_response

    llm = LLM(**default_config)  # type: ignore

    # Test that empty response raises LLMNoResponseError
    messages = [{"role": "user", "content": "Hello"}]
    with pytest.raises(LLMNoResponseError):
        llm.completion(messages=messages)


def test_response_latency_tracking(default_config):
    """Test response latency tracking in metrics."""
    metrics = Metrics(model_name="test-model")

    # Add some latencies
    metrics.add_response_latency(0.5, "response-1")
    metrics.add_response_latency(1.2, "response-2")
    metrics.add_response_latency(0.8, "response-3")

    latencies = metrics.response_latencies
    assert len(latencies) == 3
    assert latencies[0].latency == 0.5
    assert latencies[1].latency == 1.2
    assert latencies[2].latency == 0.8

    # Test negative latency is converted to 0
    metrics.add_response_latency(-0.1, "response-4")
    assert metrics.response_latencies[-1].latency == 0.0


def test_token_usage_context_window():
    """Test token usage with context window tracking."""
    usage = TokenUsage(
        model="test-model",
        prompt_tokens=100,
        completion_tokens=50,
        context_window=4096,
        response_id="test-response",
    )

    assert usage.context_window == 4096
    assert usage.per_turn_token == 0  # Default value

    # Test addition preserves max context window
    usage2 = TokenUsage(
        model="test-model",
        prompt_tokens=200,
        completion_tokens=75,
        context_window=8192,
        response_id="test-response-2",
    )

    combined = usage + usage2
    assert combined.context_window == 8192  # Should take the max
    assert combined.prompt_tokens == 300
    assert combined.completion_tokens == 125
