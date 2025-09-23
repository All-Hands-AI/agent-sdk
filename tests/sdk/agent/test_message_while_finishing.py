"""Test for handling user messages sent while agent is finishing.

This test demonstrates the issue where user messages sent to a conversation
while the conversation is processing its final step are added to the conversation
state event queue but never read by the agent or LLM because the conversation
ends without calling step() again.

Expected behavior: if messages are appended to the conversation.state.events queue
but are never read by the LLM, those unattended user messages should be concatenated
together in a single message and sent back to the agent.
"""

from unittest.mock import patch

from litellm.types.utils import (
    ChatCompletionMessageToolCall,
    Choices,
    Function,
    Message as LiteLLMMessage,
    ModelResponse,
    Usage,
)
from pydantic import SecretStr

from openhands.sdk.agent import Agent
from openhands.sdk.conversation import Conversation
from openhands.sdk.event import MessageEvent
from openhands.sdk.llm import LLM


@patch("openhands.sdk.llm.llm.litellm_completion")
def test_message_while_finishing(mock_completion):
    """Test that user messages sent while agent is finishing are processed."""

    # Track call count
    call_count = 0

    def mock_completion_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1

        if call_count == 1:
            # First call: agent finishes immediately
            tool_call = ChatCompletionMessageToolCall(
                id="call_1",
                type="function",
                function=Function(
                    name="finish", arguments='{"message": "Task completed"}'
                ),
            )

            message = LiteLLMMessage(
                role="assistant",
                content="I'll finish the task now.",
                tool_calls=[tool_call],
            )

            choice = Choices(index=0, message=message, finish_reason="tool_calls")

            return ModelResponse(
                id="response_1",
                choices=[choice],
                created=1234567890,
                model="mock",
                object="chat.completion",
                usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            )

        elif call_count == 2:
            # Second call: agent processes the unattended user message
            message = LiteLLMMessage(
                role="assistant",
                content=(
                    "I see you sent a message while I was finishing. "
                    "Thank you for your follow-up question! I'm here to help."
                ),
            )

            choice = Choices(index=0, message=message, finish_reason="stop")

            return ModelResponse(
                id="response_2",
                choices=[choice],
                created=1234567890,
                model="mock",
                object="chat.completion",
                usage=Usage(prompt_tokens=15, completion_tokens=10, total_tokens=25),
            )

        else:
            raise Exception(f"Unexpected call count: {call_count}")

    mock_completion.side_effect = mock_completion_side_effect

    # Create agent with mock LLM and finish tool
    llm = LLM(model="mock", api_key=SecretStr("test-key"))

    agent = Agent(llm=llm, tools=[])

    # Create conversation
    conversation = Conversation(agent=agent)

    # Send initial message
    conversation.send_message("Please complete this task")

    # Start the conversation - this should trigger the finish action
    conversation.run()

    # At this point, the agent should have finished
    assert conversation.state.agent_status.value == "finished"

    # Now send a message while the agent is in finished state
    # This simulates the concurrent user message scenario
    conversation.send_message("Wait, I have a follow-up question!")

    # The agent status should change from finished to idle when a new message arrives
    assert conversation.state.agent_status.value == "idle"

    # Run again - this should process the unattended message
    conversation.run()

    # Verify that the LLM was called twice
    # (finish action, then processing unattended message)
    assert call_count == 2

    # Check that the conversation contains the expected events
    events = list(conversation.state.events)

    # Find message events from user
    user_messages = [
        e for e in events if isinstance(e, MessageEvent) and e.source == "user"
    ]
    assert len(user_messages) == 2  # Initial message + follow-up

    # Find message events from agent
    agent_messages = [
        e for e in events if isinstance(e, MessageEvent) and e.source == "agent"
    ]
    # With the corrected logic, there should be only 1 agent message
    # (the response to the follow-up message)
    assert len(agent_messages) == 1

    # Verify the agent responded to the follow-up message
    last_agent_message = agent_messages[-1]
    content = last_agent_message.llm_message.content[0]
    if hasattr(content, "text"):
        text_content = content.text.lower()  # type: ignore[attr-defined]
        assert "follow-up" in text_content or "help" in text_content


@patch("openhands.sdk.llm.llm.litellm_completion")
def test_multiple_messages_while_finishing(mock_completion):
    """Test that multiple user messages sent while finishing are concatenated."""

    call_count = 0
    received_messages = []

    def mock_completion_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        received_messages.append(kwargs.get("messages", []))

        if call_count == 1:
            # First call: agent finishes immediately
            tool_call = ChatCompletionMessageToolCall(
                id="call_1",
                type="function",
                function=Function(
                    name="finish", arguments='{"message": "Task completed"}'
                ),
            )

            message = LiteLLMMessage(
                role="assistant", content="Task completed.", tool_calls=[tool_call]
            )

            choice = Choices(index=0, message=message, finish_reason="tool_calls")

            return ModelResponse(
                id="response_1",
                choices=[choice],
                created=1234567890,
                model="mock",
                object="chat.completion",
                usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            )

        elif call_count == 2:
            # Second call: agent processes the multiple unattended user messages
            message = LiteLLMMessage(
                role="assistant",
                content=(
                    "I see you sent multiple messages. "
                    "Thank you for all your follow-up messages! I'll address them all."
                ),
            )

            choice = Choices(index=0, message=message, finish_reason="stop")

            return ModelResponse(
                id="response_2",
                choices=[choice],
                created=1234567890,
                model="mock",
                object="chat.completion",
                usage=Usage(prompt_tokens=25, completion_tokens=15, total_tokens=40),
            )

    mock_completion.side_effect = mock_completion_side_effect

    # Create agent
    llm = LLM(model="mock", api_key=SecretStr("test-key"))

    agent = Agent(llm=llm, tools=[])

    # Create conversation
    conversation = Conversation(agent=agent)

    # Send initial message and run
    conversation.send_message("Complete this task")
    conversation.run()

    # Send multiple messages while finished
    conversation.send_message("First follow-up message")
    conversation.send_message("Second follow-up message")
    conversation.send_message("Third follow-up message")

    # Run again to process unattended messages
    conversation.run()

    # Verify LLM was called twice
    assert call_count == 2

    # Check that the second LLM call received the multiple user messages
    # The exact format of concatenation will depend on implementation
    second_call_messages = received_messages[1]
    user_messages_in_second_call = [
        m
        for m in second_call_messages
        if (isinstance(m, dict) and m.get("role") == "user")
        or (hasattr(m, "role") and m.role == "user")  # type: ignore[attr-defined]
    ]

    # Should have multiple user messages (the three follow-up messages)
    assert len(user_messages_in_second_call) >= 3
