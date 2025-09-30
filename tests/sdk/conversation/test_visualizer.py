"""Tests for the conversation visualizer and event visualization."""

import json
from collections.abc import Sequence

from litellm import ChatCompletionMessageToolCall
from litellm.types.utils import Function
from rich.text import Text

from openhands.sdk.conversation.visualizer import (
    ConversationVisualizer,
    create_default_visualizer,
)
from openhands.sdk.event import (
    ActionEvent,
    AgentErrorEvent,
    MessageEvent,
    ObservationEvent,
    PauseEvent,
    SystemPromptEvent,
)
from openhands.sdk.llm import ImageContent, Message, TextContent
from openhands.sdk.tool import ActionBase


class TestVisualizerMockAction(ActionBase):
    """Mock action for testing."""

    command: str = "test command"
    working_dir: str = "/tmp"


class TestVisualizerCustomAction(ActionBase):
    """Custom action with overridden visualize method."""

    task_list: list[dict] = []

    @property
    def visualize(self) -> Text:
        """Custom visualization for task tracker."""
        content = Text()
        content.append("Task Tracker Action\n", style="bold")
        content.append(f"Tasks: {len(self.task_list)}")
        for i, task in enumerate(self.task_list):
            content.append(f"\n  {i + 1}. {task.get('title', 'Untitled')}")
        return content


def create_tool_call(
    call_id: str, function_name: str, arguments: dict
) -> ChatCompletionMessageToolCall:
    """Helper to create a ChatCompletionMessageToolCall."""
    return ChatCompletionMessageToolCall(
        id=call_id,
        function=Function(name=function_name, arguments=json.dumps(arguments)),
        type="function",
    )


def test_action_base_visualize():
    """Test that ActionBase has a visualize property."""
    action = TestVisualizerMockAction(command="echo hello", working_dir="/home")

    result = action.visualize
    assert isinstance(result, Text)

    # Check that it contains action name and fields
    text_content = result.plain
    assert "TestVisualizerMockAction" in text_content
    assert "command" in text_content
    assert "echo hello" in text_content
    assert "working_dir" in text_content
    assert "/home" in text_content


def test_custom_action_visualize():
    """Test that custom actions can override visualize method."""
    tasks = [
        {"title": "Task 1", "status": "todo"},
        {"title": "Task 2", "status": "done"},
    ]
    action = TestVisualizerCustomAction(task_list=tasks)

    result = action.visualize
    assert isinstance(result, Text)

    text_content = result.plain
    assert "Task Tracker Action" in text_content
    assert "Tasks: 2" in text_content
    assert "1. Task 1" in text_content
    assert "2. Task 2" in text_content


def test_system_prompt_event_visualize():
    """Test SystemPromptEvent visualization."""
    event = SystemPromptEvent(
        system_prompt=TextContent(text="You are a helpful assistant."),
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "test_tool",
                    "description": "A test tool for demonstration",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ],
    )

    result = event.visualize
    assert isinstance(result, Text)

    text_content = result.plain
    assert "System Prompt:" in text_content
    assert "You are a helpful assistant." in text_content
    assert "Tools Available: 1" in text_content
    assert "test_tool" in text_content


def test_action_event_visualize():
    """Test ActionEvent visualization."""
    action = TestVisualizerMockAction(command="ls -la", working_dir="/tmp")
    tool_call = create_tool_call("call_123", "bash", {"command": "ls -la"})
    event = ActionEvent(
        thought=[TextContent(text="I need to list files")],
        reasoning_content="Let me check the directory contents",
        action=action,
        tool_name="bash",
        tool_call_id="call_123",
        tool_call=tool_call,
        llm_response_id="response_456",
    )

    result = event.visualize
    assert isinstance(result, Text)

    text_content = result.plain
    assert "Reasoning:" in text_content
    assert "Let me check the directory contents" in text_content
    assert "Thought:" in text_content
    assert "I need to list files" in text_content
    assert "TestVisualizerMockAction" in text_content
    assert "ls -la" in text_content


def test_observation_event_visualize():
    """Test ObservationEvent visualization."""
    from openhands.sdk.tool import ObservationBase

    class TestVisualizerMockObservation(ObservationBase):
        content: str = "Command output"

        @property
        def agent_observation(self) -> Sequence[TextContent | ImageContent]:
            return [TextContent(text=self.content)]

    observation = TestVisualizerMockObservation(
        content="total 4\ndrwxr-xr-x 2 user user 4096 Jan 1 12:00 ."
    )
    event = ObservationEvent(
        observation=observation,
        action_id="action_123",
        tool_name="bash",
        tool_call_id="call_123",
    )

    result = event.visualize
    assert isinstance(result, Text)

    text_content = result.plain
    assert "Tool: bash" in text_content
    assert "Result:" in text_content
    assert "total 4" in text_content


def test_message_event_visualize():
    """Test MessageEvent visualization."""
    message = Message(
        role="user",
        content=[TextContent(text="Hello, how can you help me?")],
    )
    event = MessageEvent(
        source="user",
        llm_message=message,
        activated_microagents=["helper", "analyzer"],
        extended_content=[TextContent(text="Additional context")],
    )

    result = event.visualize
    assert isinstance(result, Text)

    text_content = result.plain
    assert "Hello, how can you help me?" in text_content
    assert "Activated Microagents: helper, analyzer" in text_content
    assert "Prompt Extension based on Agent Context:" in text_content
    assert "Additional context" in text_content


def test_agent_error_event_visualize():
    """Test AgentErrorEvent visualization."""
    event = AgentErrorEvent(
        error="Failed to execute command: permission denied",
        tool_call_id="call_err_1",
        tool_name="execute_bash",
    )

    result = event.visualize
    assert isinstance(result, Text)

    text_content = result.plain
    assert "Error Details:" in text_content
    assert "Failed to execute command: permission denied" in text_content


def test_pause_event_visualize():
    """Test PauseEvent visualization."""
    event = PauseEvent()

    result = event.visualize
    assert isinstance(result, Text)

    text_content = result.plain
    assert "Conversation Paused" in text_content


def test_conversation_visualizer_initialization():
    """Test ConversationVisualizer can be initialized."""
    visualizer = ConversationVisualizer()
    assert visualizer is not None
    assert hasattr(visualizer, "on_event")
    assert hasattr(visualizer, "_create_event_panel")


def test_create_default_visualizer():
    """Test create_default_visualizer function."""
    visualizer = create_default_visualizer()
    assert isinstance(visualizer, ConversationVisualizer)


def test_visualizer_event_panel_creation():
    """Test that visualizer creates panels for different event types."""
    visualizer = ConversationVisualizer()

    # Test with a simple action event
    action = TestVisualizerMockAction(command="test")
    tool_call = create_tool_call("call_1", "test", {})
    event = ActionEvent(
        thought=[TextContent(text="Testing")],
        action=action,
        tool_name="test",
        tool_call_id="call_1",
        tool_call=tool_call,
        llm_response_id="response_1",
    )

    panel = visualizer._create_event_panel(event)
    assert panel is not None
    assert hasattr(panel, "renderable")


def test_metrics_formatting():
    """Test metrics subtitle formatting."""
    from openhands.sdk.conversation.conversation_stats import ConversationStats
    from openhands.sdk.llm.utils.metrics import Metrics

    # Create conversation stats with metrics
    conversation_stats = ConversationStats()

    # Create metrics and add to conversation stats
    metrics = Metrics(model_name="test-model")
    metrics.add_cost(0.0234)
    metrics.add_token_usage(
        prompt_tokens=1500,
        completion_tokens=500,
        cache_read_tokens=300,
        cache_write_tokens=0,
        reasoning_tokens=200,
        context_window=8000,
        response_id="test_response",
    )

    # Add metrics to conversation stats
    conversation_stats.service_to_metrics["test_service"] = metrics

    # Create visualizer with conversation stats
    visualizer = ConversationVisualizer(conversation_stats=conversation_stats)

    # Test the metrics subtitle formatting
    subtitle = visualizer._format_metrics_subtitle()
    assert subtitle is not None
    assert "1.50K" in subtitle  # Input tokens abbreviated
    assert "500" in subtitle  # Output tokens
    assert "20.00%" in subtitle  # Cache hit rate
    assert "200" in subtitle  # Reasoning tokens
    assert "0.0234" in subtitle  # Cost


def test_event_base_fallback_visualize():
    """Test that EventBase provides fallback visualization."""
    from openhands.sdk.event.base import EventBase
    from openhands.sdk.event.types import SourceType

    class UnknownEvent(EventBase):
        source: SourceType = "agent"

    event = UnknownEvent()
    result = event.visualize
    assert isinstance(result, Text)

    text_content = result.plain
    assert "Unknown event type: UnknownEvent" in text_content
