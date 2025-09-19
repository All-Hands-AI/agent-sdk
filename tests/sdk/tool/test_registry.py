import pytest

from openhands.sdk import register_tool
from openhands.sdk.tool import Tool
from openhands.sdk.tool.registry import resolve
from openhands.sdk.tool.schema import ActionBase, ObservationBase
from openhands.sdk.tool.spec import ToolSpec
from openhands.sdk.tool.tool import ToolExecutor


class _HelloAction(ActionBase):
    name: str


class _HelloObservation(ObservationBase):
    message: str


class _HelloExec(ToolExecutor[_HelloAction, _HelloObservation]):
    def __call__(self, action: _HelloAction) -> _HelloObservation:
        return _HelloObservation(message=f"Hello, {action.name}!")


def _hello_tool_factory() -> Tool:
    return Tool(
        name="say_hello",
        description="Says hello",
        action_type=_HelloAction,
        observation_type=_HelloObservation,
        executor=_HelloExec(),
    )


def test_register_and_resolve_callable_factory():
    register_tool("say_hello", _hello_tool_factory)
    tools = resolve(ToolSpec(name="say_hello"))
    assert len(tools) == 1
    assert isinstance(tools[0], Tool)
    assert tools[0].name == "say_hello"


def test_register_tool_instance_rejects_params():
    t = _hello_tool_factory()
    register_tool("say_hello_instance", t)
    with pytest.raises(ValueError):
        resolve(ToolSpec(name="say_hello_instance", params={"x": 1}))


def test_register_openhands_tools_removed():
    # The helper for auto-registering openhands.tools has been removed on purpose.
    # Users should explicitly register desired tools using register_tool().
    assert True
