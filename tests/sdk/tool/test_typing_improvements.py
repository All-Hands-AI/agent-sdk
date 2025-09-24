"""Tests to verify typing improvements from issue #460.

This test file verifies that the typing improvements made to eliminate
vague unions, optional runtime fields, and consumer-side narrowing work correctly.
"""

from collections.abc import Sequence

from openhands.sdk.tool import Tool
from openhands.sdk.tool.registry import register_tool, resolve_tool
from openhands.sdk.tool.spec import ToolSpec
from openhands.sdk.tool.tool import ActionBase, ObservationBase, ToolExecutor
from openhands.tools.execute_bash.definition import BashTool
from openhands.tools.str_replace_editor.definition import FileEditorTool


class MockAction(ActionBase):
    command: str


class MockObservation(ObservationBase):
    result: str


class MockExecutor(ToolExecutor[MockAction, MockObservation]):
    def __call__(self, action: MockAction) -> MockObservation:
        return MockObservation(result=f"Executed: {action.command}")


def test_tool_create_returns_sequence():
    """Test that Tool.create() always returns a Sequence, eliminating union types."""
    # Test built-in tools
    bash_tools = BashTool.create(working_dir="/tmp")
    assert isinstance(bash_tools, Sequence)
    assert len(bash_tools) == 1
    assert isinstance(bash_tools[0], BashTool)

    file_tools = FileEditorTool.create()
    assert isinstance(file_tools, Sequence)
    assert len(file_tools) == 1
    assert isinstance(file_tools[0], FileEditorTool)


def test_custom_tool_create_returns_sequence():
    """Test that custom Tool.create() implementations return Sequence."""

    class CustomTool(Tool[MockAction, MockObservation]):
        @classmethod
        def create(cls, **kwargs) -> Sequence["CustomTool"]:
            return [
                cls(
                    name="custom_tool",
                    description="A custom tool",
                    action_type=MockAction,
                    observation_type=MockObservation,
                    executor=MockExecutor(),
                    **kwargs,
                )
            ]

    tools = CustomTool.create()
    assert isinstance(tools, Sequence)
    assert len(tools) == 1
    assert isinstance(tools[0], CustomTool)


def test_registry_resolver_handles_sequence_return():
    """Test that registry resolver correctly handles Sequence return from tool factories."""  # noqa: E501

    def make_tools(**kwargs) -> Sequence[Tool]:
        return [
            Tool(
                name="test_tool",
                description="Test tool",
                action_type=MockAction,
                observation_type=MockObservation,
                executor=MockExecutor(),
            )
        ]

    # Register the tool factory
    register_tool("test_tool", make_tools)

    # Test that resolver can handle factory functions returning Sequence
    tool_spec = ToolSpec(name="test_tool", params={})
    tools = resolve_tool(tool_spec)
    assert isinstance(tools, list)
    assert len(tools) == 1
    assert tools[0].name == "test_tool"


def test_no_consumer_side_narrowing_needed():
    """Test that consumers don't need to narrow types with isinstance checks."""

    # Before the fix, consumers would need to do:
    # tools = SomeTool.create()
    # if isinstance(tools, list):
    #     for tool in tools:
    #         # use tool
    # else:
    #     # use single tool

    # After the fix, consumers can directly iterate:
    bash_tools = BashTool.create(working_dir="/tmp")
    for tool in bash_tools:
        assert hasattr(tool, "name")
        assert hasattr(tool, "description")
        assert isinstance(tool, BashTool)

    file_tools = FileEditorTool.create()
    for tool in file_tools:
        assert hasattr(tool, "name")
        assert hasattr(tool, "description")
        assert isinstance(tool, FileEditorTool)


def test_tool_fields_are_non_optional():
    """Test that required tool fields are non-optional at runtime."""

    tool = Tool(
        name="test_tool",
        description="Test tool",
        action_type=MockAction,
        observation_type=MockObservation,
        executor=MockExecutor(),
    )

    # These fields should always be present and non-None
    assert tool.name is not None
    assert tool.description is not None
    assert tool.action_type is not None
    assert tool.observation_type is not None
    assert tool.executor is not None

    # Type annotations should reflect this (no Optional/Union with None)
    # This is verified by static type checkers, but we can check at runtime too
    assert isinstance(tool.name, str)
    assert isinstance(tool.description, str)
    assert tool.action_type is MockAction
    assert tool.observation_type is MockObservation
    assert isinstance(tool.executor, MockExecutor)
