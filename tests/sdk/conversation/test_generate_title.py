"""Tests for the generate_title method in Conversation class."""

from unittest.mock import MagicMock, patch

import pytest

# Import LiteLLM types for proper mocking
from litellm.types.utils import Choices, Message as LiteLLMMessage, ModelResponse, Usage
from pydantic import SecretStr

from openhands.sdk.agent import Agent
from openhands.sdk.conversation import Conversation
from openhands.sdk.event.llm_convertible import MessageEvent
from openhands.sdk.io.memory import InMemoryFileStore
from openhands.sdk.llm import LLM, Message, TextContent


def create_test_agent() -> Agent:
    """Create a test agent."""
    llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"))
    return Agent(llm=llm, tools=[])


def create_user_message_event(content: str) -> MessageEvent:
    """Create a test MessageEvent with user content."""
    return MessageEvent(
        llm_message=Message(role="user", content=[TextContent(text=content)]),
        source="user",
    )


def create_mock_llm_response(content: str) -> ModelResponse:
    """Create a properly structured LiteLLM mock response."""
    # Create proper LiteLLM message
    message = LiteLLMMessage(content=content, role="assistant")

    # Create proper choice
    choice = Choices(finish_reason="stop", index=0, message=message)

    # Create proper usage
    usage = Usage(
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
    )

    # Create proper ModelResponse
    response = ModelResponse(
        id="test-id",
        choices=[choice],
        created=1234567890,
        model="gpt-4o-mini",
        object="chat.completion",
        usage=usage,
    )

    return response


@patch("openhands.sdk.llm.llm.LLM.completion")
def test_generate_title_basic(mock_completion):
    """Test basic generate_title functionality."""
    fs = InMemoryFileStore()
    agent = create_test_agent()
    conv = Conversation(agent=agent, persist_filestore=fs, visualize=False)

    # Add a user message to the conversation
    user_message = create_user_message_event("Help me create a Python script")
    conv.state.events.append(user_message)

    # Mock the LLM response
    mock_response = create_mock_llm_response("Create Python Script")
    mock_completion.return_value = mock_response

    # Generate title
    title = conv.generate_title()

    # Verify the title was generated
    assert title == "Create Python Script"
    mock_completion.assert_called_once()


def test_generate_title_no_user_messages():
    """Test generate_title raises ValueError when no user messages exist."""
    fs = InMemoryFileStore()
    agent = create_test_agent()
    conv = Conversation(agent=agent, persist_filestore=fs, visualize=False)

    # Don't add any user messages - the conversation might have system messages

    # Should raise ValueError
    with pytest.raises(
        ValueError, match="No user messages found in conversation events"
    ):
        conv.generate_title()


@patch("openhands.sdk.llm.llm.LLM.completion")
def test_generate_title_llm_error_fallback(mock_completion):
    """Test generate_title falls back to simple truncation when LLM fails."""
    fs = InMemoryFileStore()
    agent = create_test_agent()
    conv = Conversation(agent=agent, persist_filestore=fs, visualize=False)

    # Add a user message
    user_message = create_user_message_event("Fix the bug in my application")
    conv.state.events.append(user_message)

    # Mock the LLM to raise an exception
    mock_completion.side_effect = Exception("LLM error")

    # Generate title (should fall back to truncation)
    title = conv.generate_title()

    # Verify fallback title was generated
    assert title == "Fix the bug in my application"


@patch("openhands.sdk.llm.llm.LLM.completion")
def test_generate_title_with_max_length(mock_completion):
    """Test generate_title respects max_length parameter."""
    fs = InMemoryFileStore()
    agent = create_test_agent()
    conv = Conversation(agent=agent, persist_filestore=fs, visualize=False)

    # Add a user message
    user_message = create_user_message_event("Create a web application")
    conv.state.events.append(user_message)

    # Mock the LLM response with a long title
    mock_response = create_mock_llm_response(
        "Create a Complex Web Application with Database"
    )
    mock_completion.return_value = mock_response

    # Generate title with max_length=20
    title = conv.generate_title(max_length=20)

    # Verify the title was truncated
    assert len(title) <= 20
    assert title.endswith("...")


@patch("openhands.sdk.llm.llm.LLM.completion")
def test_generate_title_with_custom_llm(mock_completion):
    """Test generate_title with a custom LLM provided."""
    fs = InMemoryFileStore()
    agent = create_test_agent()
    conv = Conversation(agent=agent, persist_filestore=fs, visualize=False)

    # Add a user message
    user_message = create_user_message_event("Debug my code")
    conv.state.events.append(user_message)

    # Create a custom LLM
    custom_llm = LLM(model="gpt-3.5-turbo", api_key=SecretStr("custom-key"))

    # Mock the custom LLM response
    mock_response = create_mock_llm_response("Debug Code Issue")
    mock_completion.return_value = mock_response

    # Generate title with custom LLM
    title = conv.generate_title(llm=custom_llm)

    # Verify the title was generated
    assert title == "Debug Code Issue"


@patch("openhands.sdk.llm.llm.LLM.completion")
def test_generate_title_empty_llm_response_fallback(mock_completion):
    """Test generate_title falls back when LLM returns empty response."""
    fs = InMemoryFileStore()
    agent = create_test_agent()
    conv = Conversation(agent=agent, persist_filestore=fs, visualize=False)

    # Add a user message
    user_message = create_user_message_event("Help with testing")
    conv.state.events.append(user_message)

    # Mock the LLM response with empty content
    mock_response = MagicMock()
    mock_response.choices = []
    mock_completion.return_value = mock_response

    # Generate title (should fall back to truncation)
    title = conv.generate_title()

    # Verify fallback title was generated
    assert title == "Help with testing"
