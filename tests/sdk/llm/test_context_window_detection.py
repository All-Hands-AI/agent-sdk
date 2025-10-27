"""Test context window exceeded exception detection."""

from unittest.mock import patch

import pytest
from litellm.exceptions import BadRequestError, ContextWindowExceededError
from pydantic import SecretStr

from openhands.sdk.llm import LLM, Message, TextContent


def test_litellm_context_window_exceeded_error():
    """Test detection of LiteLLM's ContextWindowExceededError."""
    error = ContextWindowExceededError(
        message="Context window exceeded",
        model="gpt-4",
        llm_provider="openai",
    )
    assert LLM.is_context_window_exceeded_exception(error)


def test_anthropic_input_length_max_tokens_exceed_context_limit():
    """Test detection of Anthropic's context limit error from benchmarks issue #45.

    This tests the specific error pattern reported in:
    https://github.com/OpenHands/benchmarks/issues/45

    Error message: "input length and `max_tokens` exceed context limit: 142123 +
    64000 > 200000, decrease input length or `max_tokens` and try again"
    """
    error_message = (
        "litellm.BadRequestError: AnthropicException - "
        '{"type":"error","error":{"type":"invalid_request_error",'
        '"message":"input length and `max_tokens` exceed context limit: 142123 + '
        '64000 > 200000, decrease input length or `max_tokens` and try again"}}'
    )
    error = BadRequestError(
        message=error_message,
        model="claude-sonnet-4-20250514",
        llm_provider="anthropic",
    )
    assert LLM.is_context_window_exceeded_exception(error)


def test_prompt_too_long_error():
    """Test detection of 'prompt is too long' error pattern."""
    error = BadRequestError(
        message="Error: prompt is too long: 150000 tokens exceeds maximum of 128000",
        model="gpt-4",
        llm_provider="openai",
    )
    assert LLM.is_context_window_exceeded_exception(error)


def test_please_reduce_length_error():
    """Test detection of 'please reduce the length of' error pattern."""
    error = BadRequestError(
        message="Please reduce the length of the messages or completion",
        model="gpt-4",
        llm_provider="openai",
    )
    assert LLM.is_context_window_exceeded_exception(error)


def test_request_exceeds_context_size_error():
    """Test detection of 'request exceeds context size' error pattern."""
    error = BadRequestError(
        message="The request exceeds the available context size",
        model="gpt-4",
        llm_provider="openai",
    )
    assert LLM.is_context_window_exceeded_exception(error)


def test_context_length_exceeded_error():
    """Test detection of 'context length exceeded' error pattern."""
    error = BadRequestError(
        message="Error: context length exceeded",
        model="gpt-4",
        llm_provider="openai",
    )
    assert LLM.is_context_window_exceeded_exception(error)


def test_sambanova_maximum_context_length_error():
    """Test detection of SambaNova's specific error pattern."""
    error = BadRequestError(
        message="SambaNovaException: maximum context length is 8192 tokens",
        model="sambanova-model",
        llm_provider="sambanova",
    )
    assert LLM.is_context_window_exceeded_exception(error)


def test_case_insensitive_matching():
    """Test that error pattern matching is case-insensitive."""
    error = BadRequestError(
        message="ERROR: CONTEXT LENGTH EXCEEDED",
        model="gpt-4",
        llm_provider="openai",
    )
    assert LLM.is_context_window_exceeded_exception(error)


def test_non_context_window_bad_request_error():
    """Test that non-context-window BadRequestErrors are not detected."""
    error = BadRequestError(
        message="Invalid parameter: temperature must be between 0 and 2",
        model="gpt-4",
        llm_provider="openai",
    )
    assert not LLM.is_context_window_exceeded_exception(error)


def test_non_context_window_openai_error():
    """Test that non-context-window OpenAIErrors are not detected."""
    error = BadRequestError(
        message="API key is invalid",
        model="gpt-4",
        llm_provider="openai",
    )
    assert not LLM.is_context_window_exceeded_exception(error)


def test_unrelated_exception_type():
    """Test that unrelated exception types are not detected."""
    error = ValueError("Some unrelated error")
    assert not LLM.is_context_window_exceeded_exception(error)


def test_completion_converts_context_window_error():
    """Test that completion() converts detected context window errors.

    Detected errors should be converted to ContextWindowExceededError.
    """
    llm = LLM(model="gpt-4", api_key=SecretStr("test-key"))
    messages = [Message(role="user", content=[TextContent(text="Hello")])]

    # Mock the _one_attempt to raise an Anthropic BadRequestError
    anthropic_error = BadRequestError(
        message=(
            "litellm.BadRequestError: AnthropicException - "
            '{"type":"error","error":{"type":"invalid_request_error",'
            '"message":"input length and `max_tokens` exceed context limit: 142123 + '
            '64000 > 200000, decrease input length or `max_tokens` and try again"}}'
        ),
        model="claude-sonnet-4-20250514",
        llm_provider="anthropic",
    )

    with patch.object(llm, "_transport_call", side_effect=anthropic_error):
        with pytest.raises(ContextWindowExceededError) as exc_info:
            llm.completion(messages=messages)

        # Verify the error was converted and contains the original message
        assert "input length and `max_tokens` exceed context limit" in str(
            exc_info.value
        )
        assert exc_info.value.model == "gpt-4"


def test_responses_converts_context_window_error():
    """Test that responses() converts detected context window errors.

    Detected errors should be converted to ContextWindowExceededError.
    """
    llm = LLM(model="gpt-4", api_key=SecretStr("test-key"))
    messages = [Message(role="user", content=[TextContent(text="Hello")])]

    # Mock to raise a context window error
    context_error = BadRequestError(
        message="Error: context length exceeded",
        model="gpt-4",
        llm_provider="openai",
    )

    with patch("openhands.sdk.llm.llm.litellm_responses", side_effect=context_error):
        with pytest.raises(ContextWindowExceededError) as exc_info:
            llm.responses(messages=messages)

        # Verify the error was converted
        assert "context length exceeded" in str(exc_info.value)
        assert exc_info.value.model == "gpt-4"
