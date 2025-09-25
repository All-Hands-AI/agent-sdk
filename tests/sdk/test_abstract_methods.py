"""Test that abstract methods are properly decorated and enforced."""

from collections.abc import Sequence

import pytest

from openhands.sdk.agent.base import AgentBase
from openhands.sdk.llm.message import BaseContent, ImageContent, TextContent
from openhands.sdk.tool.schema import ActionBase, ObservationBase
from openhands.sdk.tool.tool import ToolBase, ToolExecutor


def test_agent_base_cannot_be_instantiated():
    """Test that AgentBase cannot be instantiated due to abstract step method."""
    with pytest.raises(TypeError, match="Can't instantiate abstract class AgentBase"):
        AgentBase()  # type: ignore[abstract]


def test_tool_executor_cannot_be_instantiated():
    """Test that ToolExecutor cannot be instantiated due to abstract __call__."""
    with pytest.raises(
        TypeError, match="Can't instantiate abstract class ToolExecutor"
    ):
        ToolExecutor()  # type: ignore[abstract]


def test_tool_base_cannot_be_instantiated():
    """Test that ToolBase cannot be instantiated due to abstract create method."""
    with pytest.raises(TypeError, match="Can't instantiate abstract class ToolBase"):
        ToolBase(  # type: ignore[abstract]
            name="test",
            description="test",
            action_type=type("TestAction", (), {}),  # type: ignore[arg-type]
        )


def test_observation_base_cannot_be_instantiated():
    """Test that ObservationBase cannot be instantiated due to abstract method."""
    with pytest.raises(
        TypeError, match="Can't instantiate abstract class ObservationBase"
    ):
        ObservationBase()  # type: ignore[abstract]


def test_base_content_cannot_be_instantiated():
    """Test that BaseContent cannot be instantiated due to abstract method."""
    with pytest.raises(TypeError, match="Can't instantiate abstract class BaseContent"):
        BaseContent()  # type: ignore[abstract]


def test_concrete_implementations_work():
    """Test that concrete implementations of abstract classes work correctly."""
    from openhands.sdk.tool.schema import ObservationBase

    # TextContent should work since it implements to_llm_dict
    text_content = TextContent(text="test")
    assert text_content.to_llm_dict() == [{"type": "text", "text": "test"}]

    # Create concrete subclasses for testing
    class ConcreteAction(ActionBase):
        kind: str = "ConcreteAction"

    class ConcreteObservation(ObservationBase):
        kind: str = "ConcreteObservation"

        @property
        def agent_observation(self) -> Sequence[TextContent | ImageContent]:
            return [TextContent(text="test observation")]

    # Test that concrete implementations work
    action = ConcreteAction()
    assert action is not None
    assert hasattr(action, "visualize")

    observation = ConcreteObservation()
    assert observation.agent_observation == [TextContent(text="test observation")]
