"""
Unit tests for agent status transitions.

Tests that the agent correctly transitions to RUNNING status when run() is called
from both IDLE and PAUSED states.

This addresses the fix for issue #865 where the agent status was not transitioning
to RUNNING when run() was called from IDLE state.
"""

import threading
from collections.abc import Sequence
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
from openhands.sdk.conversation.state import AgentExecutionStatus
from openhands.sdk.event import MessageEvent
from openhands.sdk.llm import LLM, ImageContent, Message, TextContent
from openhands.sdk.tool import (
    Action,
    Observation,
    ToolDefinition,
    ToolExecutor,
    register_tool,
)


class StatusTransitionMockAction(Action):
    """Mock action schema for testing."""

    command: str


class StatusTransitionMockObservation(Observation):
    """Mock observation schema for testing."""

    result: str

    @property
    def to_llm_content(self) -> Sequence[TextContent | ImageContent]:
        return [TextContent(text=self.result)]


class StatusCheckingExecutor(
    ToolExecutor[StatusTransitionMockAction, StatusTransitionMockObservation]
):
    """Executor that captures the agent status when executed."""

    def __init__(self, status_during_execution: list[AgentExecutionStatus]):
        self.status_during_execution: list[AgentExecutionStatus] = (
            status_during_execution
        )

    def __call__(
        self, action: StatusTransitionMockAction, conversation=None
    ) -> StatusTransitionMockObservation:
        # Capture the agent status during execution
        if conversation:
            self.status_during_execution.append(conversation.state.agent_status)
        return StatusTransitionMockObservation(result=f"Executed: {action.command}")


@patch("openhands.sdk.llm.llm.litellm_completion")
def test_agent_status_transitions_to_running_from_idle(mock_completion):
    """Test that agent status transitions to RUNNING when run() is called from IDLE."""
    status_during_execution: list[AgentExecutionStatus] = []

    def _make_tool(conv_state=None, **params) -> Sequence[ToolDefinition]:
        return [
            ToolDefinition(
                name="test_tool",
                description="A test tool",
                action_type=StatusTransitionMockAction,
                observation_type=StatusTransitionMockObservation,
                executor=StatusCheckingExecutor(status_during_execution),
            )
        ]

    register_tool("test_tool", _make_tool)

    llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"), usage_id="test-llm")
    agent = Agent(llm=llm, tools=[])
    conversation = Conversation(agent=agent)

    # Verify initial state is IDLE
    assert conversation.state.agent_status == AgentExecutionStatus.IDLE

    # Mock LLM to return a message that finishes execution
    mock_completion.return_value = ModelResponse(
        id="response_msg",
        choices=[
            Choices(message=LiteLLMMessage(role="assistant", content="Task completed"))
        ],
        created=0,
        model="test-model",
        object="chat.completion",
    )

    # Send message and run
    conversation.send_message(Message(role="user", content=[TextContent(text="Hello")]))
    conversation.run()

    # After run completes, status should be FINISHED
    assert conversation.state.agent_status == AgentExecutionStatus.FINISHED

    # Verify we have agent response
    agent_messages = [
        event
        for event in conversation.state.events
        if isinstance(event, MessageEvent) and event.source == "agent"
    ]
    assert len(agent_messages) == 1


@patch("openhands.sdk.llm.llm.litellm_completion")
def test_agent_status_is_running_during_execution_from_idle(mock_completion):
    """Test that agent status is RUNNING during execution when started from IDLE."""
    status_during_execution: list[AgentExecutionStatus] = []
    execution_started = threading.Event()

    def _make_tool(conv_state=None, **params) -> Sequence[ToolDefinition]:
        return [
            ToolDefinition(
                name="test_tool",
                description="A test tool",
                action_type=StatusTransitionMockAction,
                observation_type=StatusTransitionMockObservation,
                executor=StatusCheckingExecutor(status_during_execution),
            )
        ]

    register_tool("test_tool", _make_tool)

    llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"), usage_id="test-llm")
    agent = Agent(
        llm=llm,
        tools=[{"name": "test_tool"}],
    )
    conversation = Conversation(agent=agent)

    # Verify initial state is IDLE
    assert conversation.state.agent_status == AgentExecutionStatus.IDLE

    # Mock LLM to return an action first, then finish
    tool_call = ChatCompletionMessageToolCall(
        id="call_1",
        type="function",
        function=Function(
            name="test_tool",
            arguments='{"command": "test_command"}',
        ),
    )

    call_count = [0]

    def side_effect(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            # First call: return tool call
            execution_started.set()
            return ModelResponse(
                id="response_action",
                choices=[
                    Choices(
                        message=LiteLLMMessage(
                            role="assistant",
                            content="",
                            tool_calls=[tool_call],
                        )
                    )
                ],
                created=0,
                model="test-model",
                object="chat.completion",
            )
        else:
            # Second call: finish
            return ModelResponse(
                id="response_msg",
                choices=[
                    Choices(
                        message=LiteLLMMessage(
                            role="assistant", content="Task completed"
                        )
                    )
                ],
                created=0,
                model="test-model",
                object="chat.completion",
            )

    mock_completion.side_effect = side_effect

    # Send message
    conversation.send_message(
        Message(role="user", content=[TextContent(text="Execute command")])
    )

    # Run in a separate thread so we can check status during execution
    status_checked = threading.Event()
    run_complete = threading.Event()
    status_during_run = [None]

    def run_agent():
        conversation.run()
        run_complete.set()

    t = threading.Thread(target=run_agent, daemon=True)
    t.start()

    # Wait for execution to start
    assert execution_started.wait(timeout=2.0), "Execution never started"

    # Check status while running
    status_during_run[0] = conversation.state.agent_status
    status_checked.set()

    # Wait for run to complete
    assert run_complete.wait(timeout=2.0), "Run did not complete"
    t.join(timeout=0.1)

    # Verify status was RUNNING during execution
    assert status_during_run[0] == AgentExecutionStatus.RUNNING, (
        f"Expected RUNNING status during execution, got {status_during_run[0]}"
    )

    # After run completes, status should be FINISHED
    assert conversation.state.agent_status == AgentExecutionStatus.FINISHED


@patch("openhands.sdk.llm.llm.litellm_completion")
def test_agent_status_transitions_to_running_from_paused(mock_completion):
    """Test that agent status transitions to RUNNING when run() is called from
    PAUSED."""
    llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"), usage_id="test-llm")
    agent = Agent(llm=llm, tools=[])
    conversation = Conversation(agent=agent)

    # Pause the conversation
    conversation.pause()
    assert conversation.state.agent_status == AgentExecutionStatus.PAUSED

    # Mock LLM to return a message that finishes execution
    mock_completion.return_value = ModelResponse(
        id="response_msg",
        choices=[
            Choices(message=LiteLLMMessage(role="assistant", content="Task completed"))
        ],
        created=0,
        model="test-model",
        object="chat.completion",
    )

    # Send message and run
    conversation.send_message(Message(role="user", content=[TextContent(text="Hello")]))
    conversation.run()

    # After run completes, status should be FINISHED
    assert conversation.state.agent_status == AgentExecutionStatus.FINISHED

    # Verify we have agent response
    agent_messages = [
        event
        for event in conversation.state.events
        if isinstance(event, MessageEvent) and event.source == "agent"
    ]
    assert len(agent_messages) == 1
