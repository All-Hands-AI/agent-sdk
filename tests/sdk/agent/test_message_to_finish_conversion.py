"""
Test that agent messages are converted to FinishActionEvent instead of MessageEvent.

This test verifies the fix for issue #312 where MessageEvent from agent
should be merged with FinishActionEvent for consistency.
"""

from unittest.mock import patch

from litellm.types.utils import (
    Choices,
    Message as LiteLLMMessage,
    ModelResponse,
)
from pydantic import SecretStr

from openhands.sdk.agent import Agent
from openhands.sdk.conversation import Conversation
from openhands.sdk.conversation.state import AgentExecutionStatus
from openhands.sdk.event import ActionEvent, MessageEvent
from openhands.sdk.llm import LLM, Message, TextContent
from openhands.sdk.llm.utils.metrics import TokenUsage
from openhands.sdk.tool.builtins.finish import FinishAction


def test_agent_message_converted_to_finish_action():
    """Test that when LLM returns a plain message, it gets converted to FinishAction."""
    # Setup
    llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"))
    agent = Agent(llm=llm, tools=[])
    conversation = Conversation(agent=agent)

    # Mock LLM response with just a message (no tool calls)
    mock_response = ModelResponse(
        id="test-response-id",
        choices=[
            Choices(
                finish_reason="stop",
                index=0,
                message=LiteLLMMessage(
                    content="I have completed the task successfully!",
                    role="assistant",
                    tool_calls=None,
                ),
            )
        ],
        created=1234567890,
        model="gpt-4o-mini",
        object="chat.completion",
        usage=TokenUsage(
            completion_tokens=10,
            prompt_tokens=20,
        ),
    )

    # Mock the LLM completion call
    with patch("openhands.sdk.llm.llm.litellm_completion", return_value=mock_response):
        conversation.send_message(
            Message(role="user", content=[TextContent(text="Please help me")])
        )
        conversation.run()

    # Verify agent status is FINISHED
    assert conversation.state.agent_status == AgentExecutionStatus.FINISHED

    # Verify no MessageEvent from agent exists
    agent_message_events = [
        e
        for e in conversation.state.events
        if isinstance(e, MessageEvent) and e.source == "agent"
    ]
    assert len(agent_message_events) == 0, "Agent should not produce MessageEvent"

    # Verify FinishActionEvent exists instead
    finish_action_events = [
        e
        for e in conversation.state.events
        if isinstance(e, ActionEvent)
        and e.source == "agent"
        and e.tool_name == "finish"
    ]
    assert len(finish_action_events) == 1, "Should have exactly one FinishActionEvent"

    finish_event = finish_action_events[0]
    assert isinstance(finish_event.action, FinishAction)
    assert finish_event.action.message == "I have completed the task successfully!"
    assert (
        finish_event.tool_call_id is None
    )  # No tool call ID for manually simulated actions
    assert finish_event.llm_response_id == "test-response-id"

    # Verify the finish action was executed (should have corresponding observation)
    from openhands.sdk.event import ObservationEvent

    finish_observations = [
        e
        for e in conversation.state.events
        if isinstance(e, ObservationEvent)
        and e.tool_name == "finish"
        and e.action_id == finish_event.id
    ]
    assert len(finish_observations) == 1, "FinishAction should have been executed"


def test_user_message_still_creates_message_event():
    """Test that user messages still create MessageEvent
    (not converted to FinishAction)."""
    # Setup
    llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"))
    agent = Agent(llm=llm, tools=[])
    conversation = Conversation(agent=agent)

    # Send user message
    user_message = Message(
        role="user", content=[TextContent(text="Hello, please help me")]
    )
    conversation.send_message(user_message)

    # Verify user MessageEvent exists
    user_message_events = [
        e
        for e in conversation.state.events
        if isinstance(e, MessageEvent) and e.source == "user"
    ]
    assert len(user_message_events) == 1, "User should still produce MessageEvent"

    user_event = user_message_events[0]
    assert isinstance(user_event.llm_message.content[0], TextContent)
    assert user_event.llm_message.content[0].text == "Hello, please help me"

    # Verify user MessageEvent has no metrics field (since it's not from agent)
    assert not hasattr(user_event, "metrics")


def test_empty_agent_message_gets_default_finish_message():
    """Test that empty agent message gets default 'Task completed' message."""
    # Setup
    llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"))
    agent = Agent(llm=llm, tools=[])
    conversation = Conversation(agent=agent)

    # Mock LLM response with empty content
    mock_response = ModelResponse(
        id="test-response-id",
        choices=[
            Choices(
                finish_reason="stop",
                index=0,
                message=LiteLLMMessage(
                    content="",  # Empty content
                    role="assistant",
                    tool_calls=None,
                ),
            )
        ],
        created=1234567890,
        model="gpt-4o-mini",
        object="chat.completion",
        usage=TokenUsage(
            completion_tokens=1,
            prompt_tokens=20,
        ),
    )

    # Mock the LLM completion call
    with patch("openhands.sdk.llm.llm.litellm_completion", return_value=mock_response):
        conversation.send_message(
            Message(role="user", content=[TextContent(text="Please help me")])
        )
        conversation.run()

    # Verify FinishActionEvent with default message
    finish_action_events = [
        e
        for e in conversation.state.events
        if isinstance(e, ActionEvent)
        and e.source == "agent"
        and e.tool_name == "finish"
    ]
    assert len(finish_action_events) == 1

    finish_event = finish_action_events[0]
    assert isinstance(finish_event.action, FinishAction)
    assert finish_event.action.message == "Task completed"
