from unittest.mock import Mock

import pytest
from pydantic import Field

from openhands.sdk.tool import Observation, ToolDefinition, ToolExecutor
from openhands.sdk.tool.schema import Action


def create_mock_conversation():
    """Create a mock conversation for testing."""
    mock_conversation = Mock()
    mock_conversation.id = "test-conversation-id"
    return mock_conversation


class OCAAction(Action):
    y: int = Field(description="y")


class OCAObs(Observation):
    value: int

    @property
    def to_llm_content(self):  # type: ignore[override]
        from openhands.sdk.llm import TextContent

        return [TextContent(text=str(self.value))]


def test_tool_call_with_observation_none_result_shapes():
    # When observation_type is None, results are wrapped/coerced to Observation
    # 1) dict -> Observation
    class E1(ToolExecutor[OCAAction, dict[str, object]]):
        def __call__(self, action: OCAAction, conversation) -> dict[str, object]:  # noqa: ARG002
            return {"kind": "OCAObs", "value": 1}

    t = ToolDefinition(
        name="t",
        description="d",
        action_type=OCAAction,
        observation_type=None,
        executor=E1(),
    )
    obs = t(OCAAction(y=1), create_mock_conversation())
    assert isinstance(obs, Observation)

    # 2) Observation subclass -> Observation passthrough
    class MObs(Observation):
        value: int

        @property
        def to_llm_content(self):  # type: ignore[override]
            from openhands.sdk.llm import TextContent

            return [TextContent(text=str(self.value))]

    class E2(ToolExecutor[OCAAction, MObs]):
        def __call__(self, action: OCAAction, conversation) -> MObs:  # noqa: ARG002
            return MObs(value=2)

    t2 = ToolDefinition(
        name="t2",
        description="d",
        action_type=OCAAction,
        observation_type=None,
        executor=E2(),
    )
    obs2 = t2(OCAAction(y=2), create_mock_conversation())
    assert isinstance(obs2, Observation)
    assert isinstance(obs2, MObs)

    # 3) invalid type -> raises TypeError
    class E3(ToolExecutor[OCAAction, list[int]]):
        def __call__(self, action: OCAAction, conversation) -> list[int]:  # noqa: ARG002
            return [1, 2, 3]

    t3 = ToolDefinition(
        name="t3",
        description="d",
        action_type=OCAAction,
        observation_type=None,
        executor=E3(),
    )
    with pytest.raises(TypeError, match="Output must be dict or BaseModel"):
        t3(OCAAction(y=3), create_mock_conversation())
