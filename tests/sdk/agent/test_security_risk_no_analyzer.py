"""Test agent behavior when tool response contains security_risk param but no security analyzer is configured."""

from unittest.mock import patch

from litellm import ChatCompletionMessageToolCall
from litellm.types.utils import (
    Choices,
    Function,
    Message as LiteLLMMessage,
    ModelResponse,
)
from pydantic import SecretStr

from openhands.sdk.agent import Agent
from openhands.sdk.conversation import Conversation
from openhands.sdk.event import ActionEvent
from openhands.sdk.llm import LLM, Message, TextContent


def test_security_risk_param_ignored_when_no_analyzer():
    """Test that security_risk param is ignored when no security analyzer is configured."""
    # Create agent without security analyzer (using only built-in tools)
    llm = LLM(
        service_id="test-llm",
        model="test-model",
        api_key=SecretStr("test-key"),
        base_url="http://test",
    )
    
    agent = Agent(llm=llm, tools=[])

    # Mock LLM response that includes security_risk parameter
    def mock_llm_response(messages, **kwargs):
        return ModelResponse(
            id="mock-response-1",
            choices=[
                Choices(
                    index=0,
                    message=LiteLLMMessage(
                        role="assistant",
                        content="I'll think about this with security_risk parameter.",
                        tool_calls=[
                            ChatCompletionMessageToolCall(
                                id="call_1",
                                type="function",
                                function=Function(
                                    name="think",
                                    arguments='{"thought": "This is a test thought", "security_risk": "LOW"}',
                                ),
                            )
                        ],
                    ),
                    finish_reason="tool_calls",
                )
            ],
            created=0,
            model="test-model",
            object="chat.completion",
        )

    collected_events = []

    def event_callback(event):
        collected_events.append(event)

    conversation = Conversation(agent=agent, callbacks=[event_callback])

    with patch(
        "openhands.sdk.llm.llm.litellm_completion", side_effect=mock_llm_response
    ):
        # Send a message to start the conversation
        conversation.send_message(
            Message(
                role="user",
                content=[TextContent(text="Please think about something")],
            )
        )

        # Run one step to trigger the tool call
        agent.step(conversation.state, on_event=event_callback)

    # Verify that the tool executed successfully (no error events)
    from openhands.sdk.event import AgentErrorEvent
    error_events = [e for e in collected_events if isinstance(e, AgentErrorEvent)]
    assert len(error_events) == 0, (
        f"Expected no error events, but got: {[e.error for e in error_events]}"
    )

    # Verify that an ActionEvent was created for the think command
    action_events = [e for e in collected_events if isinstance(e, ActionEvent)]
    assert len(action_events) >= 1, "Expected at least one ActionEvent"
    
    # Find the think execution event
    think_events = [e for e in action_events if e.tool == "think"]
    assert len(think_events) == 1, f"Expected exactly one think event, got {len(think_events)}"
    
    think_event = think_events[0]
    assert think_event.action.thought == "This is a test thought"
    
    # Verify that security_risk was not passed to the tool action
    # (it should have been popped from arguments)
    assert not hasattr(think_event.action, "security_risk")


def test_security_risk_param_ignored_with_multiple_tools():
    """Test that security_risk param is ignored across multiple tool calls when no analyzer is configured."""
    # Create agent without security analyzer (using only built-in tools)
    llm = LLM(
        service_id="test-llm",
        model="test-model",
        api_key=SecretStr("test-key"),
        base_url="http://test",
    )
    
    agent = Agent(llm=llm, tools=[])

    call_count = 0

    def mock_llm_response(messages, **kwargs):
        nonlocal call_count
        call_count += 1
        
        if call_count == 1:
            # First call with security_risk
            return ModelResponse(
                id="mock-response-1",
                choices=[
                    Choices(
                        index=0,
                        message=LiteLLMMessage(
                            role="assistant",
                            content="First thought with security_risk.",
                            tool_calls=[
                                ChatCompletionMessageToolCall(
                                    id="call_1",
                                    type="function",
                                    function=Function(
                                        name="think",
                                        arguments='{"thought": "First thought", "security_risk": "MEDIUM"}',
                                    ),
                                )
                            ],
                        ),
                        finish_reason="tool_calls",
                    )
                ],
                created=0,
                model="test-model",
                object="chat.completion",
            )
        else:
            # Second call also with security_risk
            return ModelResponse(
                id="mock-response-2",
                choices=[
                    Choices(
                        index=0,
                        message=LiteLLMMessage(
                            role="assistant",
                            content="Second thought with security_risk.",
                            tool_calls=[
                                ChatCompletionMessageToolCall(
                                    id="call_2",
                                    type="function",
                                    function=Function(
                                        name="think",
                                        arguments='{"thought": "Second thought", "security_risk": "HIGH"}',
                                    ),
                                )
                            ],
                        ),
                        finish_reason="tool_calls",
                    )
                ],
                created=0,
                model="test-model",
                object="chat.completion",
            )

    collected_events = []

    def event_callback(event):
        collected_events.append(event)

    conversation = Conversation(agent=agent, callbacks=[event_callback])

    with patch(
        "openhands.sdk.llm.llm.litellm_completion", side_effect=mock_llm_response
    ):
        conversation.send_message(
            Message(
                role="user",
                content=[TextContent(text="Think about two things")],
            )
        )

        # Run first step
        agent.step(conversation.state, on_event=event_callback)
        
        # Run second step
        agent.step(conversation.state, on_event=event_callback)

    # Verify no error events occurred
    from openhands.sdk.event import AgentErrorEvent
    error_events = [e for e in collected_events if isinstance(e, AgentErrorEvent)]
    assert len(error_events) == 0, (
        f"Expected no error events, but got: {[e.error for e in error_events]}"
    )

    # Verify both think commands executed
    action_events = [e for e in collected_events if isinstance(e, ActionEvent)]
    think_events = [e for e in action_events if e.tool == "think"]
    assert len(think_events) == 2, f"Expected exactly two think events, got {len(think_events)}"
    
    # Verify the thoughts were executed correctly
    thoughts = [event.action.thought for event in think_events]
    assert "First thought" in thoughts
    assert "Second thought" in thoughts


def test_security_risk_param_with_invalid_value_ignored():
    """Test that invalid security_risk values are ignored when no analyzer is configured."""
    # Create agent without security analyzer (using only built-in tools)
    llm = LLM(
        service_id="test-llm",
        model="test-model",
        api_key=SecretStr("test-key"),
        base_url="http://test",
    )
    
    agent = Agent(llm=llm, tools=[])

    # Mock LLM response with invalid security_risk value
    def mock_llm_response(messages, **kwargs):
        return ModelResponse(
            id="mock-response-1",
            choices=[
                Choices(
                    index=0,
                    message=LiteLLMMessage(
                        role="assistant",
                        content="Thought with invalid security_risk value.",
                        tool_calls=[
                            ChatCompletionMessageToolCall(
                                id="call_1",
                                type="function",
                                function=Function(
                                    name="think",
                                    arguments='{"thought": "Test thought", "security_risk": "INVALID_RISK"}',
                                ),
                            )
                        ],
                    ),
                    finish_reason="tool_calls",
                )
            ],
            created=0,
            model="test-model",
            object="chat.completion",
        )

    collected_events = []

    def event_callback(event):
        collected_events.append(event)

    conversation = Conversation(agent=agent, callbacks=[event_callback])

    with patch(
        "openhands.sdk.llm.llm.litellm_completion", side_effect=mock_llm_response
    ):
        conversation.send_message(
            Message(
                role="user",
                content=[TextContent(text="Think about something")],
            )
        )

        # Run one step to trigger the tool call
        agent.step(conversation.state, on_event=event_callback)

    # Verify that the tool executed successfully despite invalid security_risk value
    from openhands.sdk.event import AgentErrorEvent
    error_events = [e for e in collected_events if isinstance(e, AgentErrorEvent)]
    assert len(error_events) == 0, (
        f"Expected no error events, but got: {[e.error for e in error_events]}"
    )

    # Verify that the think command executed
    action_events = [e for e in collected_events if isinstance(e, ActionEvent)]
    think_events = [e for e in action_events if e.tool == "think"]
    assert len(think_events) == 1, f"Expected exactly one think event, got {len(think_events)}"
    
    think_event = think_events[0]
    assert think_event.action.thought == "Test thought"