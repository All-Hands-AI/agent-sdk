"""Tests for litellm_extra_body configuration support."""

from unittest.mock import patch

import pytest
from pydantic import SecretStr

from openhands.sdk.llm import LLM, Message, TextContent

# Import common test utilities
from tests.conftest import create_mock_litellm_response


@pytest.fixture
def base_llm():
    """Base LLM for testing."""
    return LLM(
        model="litellm_proxy/claude-sonnet-4",
        api_key=SecretStr("test_key"),
        service_id="test-llm",
    )


def test_litellm_extra_body_field_initialization():
    """Test that litellm_extra_body field can be initialized."""
    extra_body_json = (
        '{"metadata": {"user_id": "test-user", "session_id": "test-session"}}'
    )

    llm = LLM(
        model="litellm_proxy/claude-sonnet-4",
        api_key=SecretStr("test_key"),
        service_id="test-llm",
        litellm_extra_body=extra_body_json,
    )

    assert llm.litellm_extra_body == extra_body_json


def test_litellm_extra_body_default_none():
    """Test that litellm_extra_body defaults to None."""
    llm = LLM(
        model="litellm_proxy/claude-sonnet-4",
        api_key=SecretStr("test_key"),
        service_id="test-llm",
    )

    assert llm.litellm_extra_body is None


@patch("openhands.sdk.llm.llm.litellm_completion")
def test_litellm_extra_body_parsing_and_merging(mock_completion, base_llm):
    """Test that litellm_extra_body is parsed and merged correctly."""
    # Setup mock response
    mock_completion.return_value = create_mock_litellm_response(
        content="Test response", model="claude-sonnet-4"
    )

    # Set up LLM with litellm_extra_body
    extra_body_json = '{"metadata": {"user_id": "test-user"}, "custom_param": "value"}'
    base_llm.litellm_extra_body = extra_body_json

    # Create test message
    messages = [Message(role="user", content=[TextContent(text="Test message")])]

    # Call completion
    base_llm.completion(messages)

    # Verify that litellm_completion was called with the parsed extra_body
    mock_completion.assert_called_once()
    call_kwargs = mock_completion.call_args[1]

    expected_extra_body = {
        "metadata": {"user_id": "test-user"},
        "custom_param": "value",
    }
    assert call_kwargs["extra_body"] == expected_extra_body


@patch("openhands.sdk.llm.llm.litellm_completion")
def test_litellm_extra_body_merges_with_existing_extra_body(mock_completion, base_llm):
    """Test that litellm_extra_body merges with existing extra_body."""
    # Setup mock response
    mock_completion.return_value = create_mock_litellm_response(
        content="Test response", model="claude-sonnet-4"
    )

    # Set up LLM with litellm_extra_body
    extra_body_json = '{"metadata": {"user_id": "test-user"}, "custom_param": "value"}'
    base_llm.litellm_extra_body = extra_body_json

    # Create test message
    messages = [Message(role="user", content=[TextContent(text="Test message")])]

    # Call completion with existing extra_body
    existing_extra_body = {
        "metadata": {"session_id": "test-session"},
        "other_param": "other",
    }
    base_llm.completion(messages, extra_body=existing_extra_body)

    # Verify that litellm_completion was called with merged extra_body
    mock_completion.assert_called_once()
    call_kwargs = mock_completion.call_args[1]

    expected_extra_body = {
        "metadata": {
            "session_id": "test-session",  # from existing
            "user_id": "test-user",  # from litellm_extra_body (should override)
        },
        "other_param": "other",  # from existing
        "custom_param": "value",  # from litellm_extra_body
    }
    assert call_kwargs["extra_body"] == expected_extra_body


@patch("openhands.sdk.llm.llm.litellm_completion")
def test_litellm_extra_body_metadata_merging(mock_completion, base_llm):
    """Test that metadata is properly merged when both sources have it."""
    # Setup mock response
    mock_completion.return_value = create_mock_litellm_response(
        content="Test response", model="claude-sonnet-4"
    )

    # Set up LLM with litellm_extra_body containing metadata
    extra_body_json = '{"metadata": {"user_id": "test-user", "trace_id": "abc123"}}'
    base_llm.litellm_extra_body = extra_body_json

    # Create test message
    messages = [Message(role="user", content=[TextContent(text="Test message")])]

    # Call completion with existing extra_body that also has metadata
    existing_extra_body = {
        "metadata": {"session_id": "test-session", "user_id": "old-user"}
    }
    base_llm.completion(messages, extra_body=existing_extra_body)

    # Verify that metadata is properly merged (litellm_extra_body should override)
    mock_completion.assert_called_once()
    call_kwargs = mock_completion.call_args[1]

    expected_metadata = {
        "session_id": "test-session",  # from existing
        "user_id": "test-user",  # from litellm_extra_body (overrides existing)
        "trace_id": "abc123",  # from litellm_extra_body
    }
    assert call_kwargs["extra_body"]["metadata"] == expected_metadata


@patch("openhands.sdk.llm.llm.litellm_completion")
@patch("openhands.sdk.llm.llm.logger")
def test_litellm_extra_body_invalid_json_warning(
    mock_logger, mock_completion, base_llm
):
    """Test that invalid JSON in litellm_extra_body logs a warning and is ignored."""
    # Setup mock response
    mock_completion.return_value = create_mock_litellm_response(
        content="Test response", model="claude-sonnet-4"
    )

    # Set up LLM with invalid JSON in litellm_extra_body
    base_llm.litellm_extra_body = '{"invalid": json}'

    # Create test message
    messages = [Message(role="user", content=[TextContent(text="Test message")])]

    # Call completion
    base_llm.completion(messages)

    # Verify that a warning was logged
    mock_logger.warning.assert_called_once()
    warning_call = mock_logger.warning.call_args[0][0]
    assert "Failed to parse litellm_extra_body as JSON" in warning_call
    assert "Ignoring custom extra_body" in warning_call

    # Verify that litellm_completion was called without extra_body
    mock_completion.assert_called_once()
    call_kwargs = mock_completion.call_args[1]
    assert "extra_body" not in call_kwargs


@patch("openhands.sdk.llm.llm.litellm_completion")
def test_litellm_extra_body_non_dict_replaces_existing(mock_completion, base_llm):
    """Test that non-dict litellm_extra_body replaces existing extra_body."""
    # Setup mock response
    mock_completion.return_value = create_mock_litellm_response(
        content="Test response", model="claude-sonnet-4"
    )

    # Set up LLM with non-dict litellm_extra_body
    extra_body_json = '"string_value"'
    base_llm.litellm_extra_body = extra_body_json

    # Create test message
    messages = [Message(role="user", content=[TextContent(text="Test message")])]

    # Call completion with existing extra_body
    existing_extra_body = {"metadata": {"session_id": "test-session"}}
    base_llm.completion(messages, extra_body=existing_extra_body)

    # Verify that litellm_completion was called with the string value
    mock_completion.assert_called_once()
    call_kwargs = mock_completion.call_args[1]
    assert call_kwargs["extra_body"] == "string_value"


@patch("openhands.sdk.llm.llm.litellm_completion")
def test_litellm_extra_body_no_existing_extra_body(mock_completion, base_llm):
    """Test that litellm_extra_body works when there's no existing extra_body."""
    # Setup mock response
    mock_completion.return_value = create_mock_litellm_response(
        content="Test response", model="claude-sonnet-4"
    )

    # Set up LLM with litellm_extra_body
    extra_body_json = '{"metadata": {"user_id": "test-user"}, "custom_param": "value"}'
    base_llm.litellm_extra_body = extra_body_json

    # Create test message
    messages = [Message(role="user", content=[TextContent(text="Test message")])]

    # Call completion without existing extra_body
    base_llm.completion(messages)

    # Verify that litellm_completion was called with the parsed extra_body
    mock_completion.assert_called_once()
    call_kwargs = mock_completion.call_args[1]

    expected_extra_body = {
        "metadata": {"user_id": "test-user"},
        "custom_param": "value",
    }
    assert call_kwargs["extra_body"] == expected_extra_body


def test_litellm_extra_body_removed_for_non_proxy_models():
    """Test that extra_body is removed for non-litellm_proxy models."""
    # Create LLM with non-proxy model
    llm = LLM(
        model="gpt-4o",  # Not a litellm_proxy model
        api_key=SecretStr("test_key"),
        service_id="test-llm",
        litellm_extra_body='{"metadata": {"user_id": "test-user"}}',
    )

    # Test the _normalize_call_kwargs method directly
    kwargs = {"extra_body": {"existing": "data"}}
    normalized_kwargs = llm._normalize_call_kwargs(kwargs, has_tools=False)

    # extra_body should be removed for non-proxy models
    assert "extra_body" not in normalized_kwargs


@patch("openhands.sdk.llm.llm.litellm_completion")
def test_litellm_extra_body_preserved_for_proxy_models(mock_completion, base_llm):
    """Test that extra_body is preserved for litellm_proxy models."""
    # Setup mock response
    mock_completion.return_value = create_mock_litellm_response(
        content="Test response", model="claude-sonnet-4"
    )

    # Set up LLM with litellm_extra_body (base_llm uses litellm_proxy model)
    extra_body_json = '{"metadata": {"user_id": "test-user"}}'
    base_llm.litellm_extra_body = extra_body_json

    # Create test message
    messages = [Message(role="user", content=[TextContent(text="Test message")])]

    # Call completion
    base_llm.completion(messages)

    # Verify that extra_body was preserved and passed to litellm_completion
    mock_completion.assert_called_once()
    call_kwargs = mock_completion.call_args[1]
    assert "extra_body" in call_kwargs
    assert call_kwargs["extra_body"]["metadata"]["user_id"] == "test-user"


def test_litellm_extra_body_serialization():
    """Test that LLM with litellm_extra_body can be serialized and deserialized."""
    extra_body_json = '{"metadata": {"user_id": "test-user"}}'

    llm = LLM(
        model="litellm_proxy/claude-sonnet-4",
        api_key=SecretStr("test_key"),
        service_id="test-llm",
        litellm_extra_body=extra_body_json,
    )

    # Test serialization
    serialized = llm.model_dump()
    assert serialized["litellm_extra_body"] == extra_body_json

    # Test deserialization
    deserialized = LLM.model_validate(serialized)
    assert deserialized.litellm_extra_body == extra_body_json



@patch("openhands.sdk.llm.llm.litellm_completion")
def test_metadata_automatically_included(mock_completion, base_llm):
    """Test that LLM metadata is automatically included in extra_body."""
    # Setup mock response
    mock_completion.return_value = create_mock_litellm_response(
        content="Test response", model="claude-sonnet-4"
    )

    # Set up LLM with metadata
    base_llm.metadata = {"session_id": "test-session", "user_id": "test-user"}

    # Create test message
    messages = [Message(role="user", content=[TextContent(text="Test message")])]

    # Call completion
    base_llm.completion(messages)

    # Verify that metadata was automatically included in extra_body
    mock_completion.assert_called_once()
    call_kwargs = mock_completion.call_args[1]

    expected_extra_body = {
        "metadata": {"session_id": "test-session", "user_id": "test-user"}
    }
    assert call_kwargs["extra_body"] == expected_extra_body


@patch("openhands.sdk.llm.llm.litellm_completion")
def test_metadata_and_litellm_extra_body_merging(mock_completion, base_llm):
    """Test that LLM metadata and litellm_extra_body are properly merged."""
    # Setup mock response
    mock_completion.return_value = create_mock_litellm_response(
        content="Test response", model="claude-sonnet-4"
    )

    # Set up LLM with both metadata and litellm_extra_body
    base_llm.metadata = {"session_id": "test-session", "trace_id": "trace-123"}
    base_llm.litellm_extra_body = '{"metadata": {"user_id": "test-user"}, "custom_param": "value"}'

    # Create test message
    messages = [Message(role="user", content=[TextContent(text="Test message")])]

    # Call completion
    base_llm.completion(messages)

    # Verify that both metadata sources were merged
    mock_completion.assert_called_once()
    call_kwargs = mock_completion.call_args[1]

    expected_extra_body = {
        "metadata": {
            "session_id": "test-session",  # from LLM metadata
            "trace_id": "trace-123",       # from LLM metadata
            "user_id": "test-user",        # from litellm_extra_body
        },
        "custom_param": "value",  # from litellm_extra_body
    }
    assert call_kwargs["extra_body"] == expected_extra_body


@patch("openhands.sdk.llm.llm.litellm_responses")
def test_metadata_automatically_included_in_responses_api(mock_responses, base_llm):
    """Test that LLM metadata is automatically included in responses API calls."""
    # Setup mock response
    mock_responses.return_value = create_mock_litellm_response(
        content="Test response", model="claude-sonnet-4"
    )

    # Set up LLM with metadata
    base_llm.metadata = {"session_id": "test-session", "user_id": "test-user"}

    # Create test message
    messages = [Message(role="user", content=[TextContent(text="Test message")])]

    # Call responses API
    base_llm.responses(messages)

    # Verify that metadata was automatically included
    mock_responses.assert_called_once()
    call_kwargs = mock_responses.call_args[1]

    expected_metadata = {"session_id": "test-session", "user_id": "test-user"}
    assert call_kwargs["metadata"] == expected_metadata
