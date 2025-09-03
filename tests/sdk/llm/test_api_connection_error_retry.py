from unittest.mock import MagicMock, patch

import pytest
from litellm.exceptions import APIConnectionError
from pydantic import SecretStr

from openhands.sdk.config import LLMConfig
from openhands.sdk.llm import LLM


def create_mock_response(content: str = "Test response", response_id: str = "test-id"):
    """Helper function to create properly structured mock responses."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = content

    # Create a more complete usage mock
    mock_usage = MagicMock()
    mock_usage.get.side_effect = lambda key, default=None: {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "model_extra": {},
    }.get(key, default)
    mock_usage.prompt_tokens_details = None

    # Mock the response.get() method
    def mock_get(key, default=None):
        if key == "choices":
            return mock_response.choices
        elif key == "usage":
            return mock_usage
        elif key == "id":
            return response_id
        return default

    mock_response.get = mock_get

    # Also support dict-like access
    def mock_getitem(self, key):
        return {
            "choices": mock_response.choices,
            "usage": mock_usage,
            "id": response_id,
        }[key]

    mock_response.__getitem__ = mock_getitem

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


@patch("openhands.sdk.llm.llm.litellm_completion")
def test_completion_retries_api_connection_error(
    mock_litellm_completion, default_config
):
    """Test that APIConnectionError is properly retried."""
    mock_response = create_mock_response("Retry successful")

    # Mock the litellm_completion to first raise an APIConnectionError,
    # then return a successful response
    mock_litellm_completion.side_effect = [
        APIConnectionError(
            message="API connection error",
            llm_provider="test_provider",
            model="test_model",
        ),
        mock_response,
    ]

    # Create an LLM instance and call completion
    llm = LLM(config=default_config, service_id="test-service")
    response = llm.completion(
        messages=[{"role": "user", "content": "Hello!"}],
    )

    # Verify that the retry was successful
    assert response == mock_response
    assert mock_litellm_completion.call_count == 2  # Initial call + 1 retry


@patch("openhands.sdk.llm.llm.litellm_completion")
def test_completion_max_retries_api_connection_error(
    mock_litellm_completion, default_config
):
    """Test that APIConnectionError respects max retries."""
    # Mock the litellm_completion to raise APIConnectionError multiple times
    mock_litellm_completion.side_effect = [
        APIConnectionError(
            message="API connection error 1",
            llm_provider="test_provider",
            model="test_model",
        ),
        APIConnectionError(
            message="API connection error 2",
            llm_provider="test_provider",
            model="test_model",
        ),
        APIConnectionError(
            message="API connection error 3",
            llm_provider="test_provider",
            model="test_model",
        ),
    ]

    # Create an LLM instance and call completion
    llm = LLM(config=default_config, service_id="test-service")

    # The completion should raise an APIConnectionError after exhausting all retries
    with pytest.raises(APIConnectionError) as excinfo:
        llm.completion(
            messages=[{"role": "user", "content": "Hello!"}],
        )

    # Verify that the correct number of retries were attempted
    # The actual behavior is that it tries num_retries times total
    assert mock_litellm_completion.call_count == default_config.num_retries

    # The exception should contain connection error information
    assert "API connection error" in str(excinfo.value)


@patch("openhands.sdk.llm.llm.litellm_completion")
def test_completion_no_retry_on_success(mock_litellm_completion, default_config):
    """Test that successful calls don't trigger retries."""
    mock_response = create_mock_response("Success on first try")
    mock_litellm_completion.return_value = mock_response

    # Create an LLM instance and call completion
    llm = LLM(config=default_config, service_id="test-service")
    response = llm.completion(
        messages=[{"role": "user", "content": "Hello!"}],
    )

    # Verify that no retries were needed
    assert response == mock_response
    assert mock_litellm_completion.call_count == 1  # Only the initial call


@patch("openhands.sdk.llm.llm.litellm_completion")
def test_completion_no_retry_on_non_retryable_error(
    mock_litellm_completion, default_config
):
    """Test that non-retryable errors don't trigger retries."""
    # Mock a non-retryable error (e.g., ValueError)
    mock_litellm_completion.side_effect = ValueError("Invalid input")

    # Create an LLM instance and call completion
    llm = LLM(config=default_config, service_id="test-service")

    # The completion should raise the ValueError immediately without retries
    with pytest.raises(ValueError) as excinfo:
        llm.completion(
            messages=[{"role": "user", "content": "Hello!"}],
        )

    # Verify that no retries were attempted
    assert mock_litellm_completion.call_count == 1  # Only the initial call
    assert "Invalid input" in str(excinfo.value)


def test_retry_configuration_validation():
    """Test that retry configuration is properly validated."""
    # Test with zero retries
    config_no_retry = LLMConfig(
        model="gpt-4o",
        api_key=SecretStr("test_key"),
        num_retries=0,
    )
    llm_no_retry = LLM(config=config_no_retry)
    assert llm_no_retry.config.num_retries == 0

    # Test with custom retry settings
    config_custom = LLMConfig(
        model="gpt-4o",
        api_key=SecretStr("test_key"),
        num_retries=5,
        retry_min_wait=2,
        retry_max_wait=10,
        retry_multiplier=2.0,
    )
    llm_custom = LLM(config=config_custom)
    assert llm_custom.config.num_retries == 5
    assert llm_custom.config.retry_min_wait == 2
    assert llm_custom.config.retry_max_wait == 10
    assert llm_custom.config.retry_multiplier == 2.0


@patch("openhands.sdk.llm.llm.litellm_completion")
def test_retry_listener_callback(mock_litellm_completion, default_config):
    """Test that retry listener callback is called during retries."""
    retry_calls = []

    def retry_listener(attempt: int, max_attempts: int):
        retry_calls.append((attempt, max_attempts))

    mock_response = create_mock_response("Success after retry")

    mock_litellm_completion.side_effect = [
        APIConnectionError(
            message="Connection failed",
            llm_provider="test_provider",
            model="test_model",
        ),
        mock_response,
    ]

    # Create an LLM instance with retry listener
    llm = LLM(config=default_config, retry_listener=retry_listener)
    response = llm.completion(
        messages=[{"role": "user", "content": "Hello!"}],
    )

    # Verify that the retry listener was called
    assert response == mock_response
    assert len(retry_calls) >= 1  # At least one retry attempt should be logged

    # Check that retry listener received correct parameters
    if retry_calls:
        attempt, max_attempts = retry_calls[0]
        assert isinstance(attempt, int)
        assert isinstance(max_attempts, int)
        assert attempt >= 1
        assert max_attempts == default_config.num_retries
