"""Test that tool_name class variables are consistent with automatic naming."""

from openhands.tools.browser_use import BrowserToolSet
from openhands.tools.execute_bash import BashTool
from openhands.tools.file_editor import FileEditorTool
from openhands.tools.glob import GlobTool
from openhands.tools.grep import GrepTool
from openhands.tools.planning_file_editor import PlanningFileEditorTool
from openhands.tools.task_tracker import TaskTrackerTool


def test_tool_name_attributes_exist():
    """Test that all tool classes have tool_name class variables."""
    tools = [
        BashTool,
        FileEditorTool,
        TaskTrackerTool,
        BrowserToolSet,
        GrepTool,
        GlobTool,
        PlanningFileEditorTool,
    ]

    for tool_class in tools:
        assert hasattr(tool_class, "tool_name"), (
            f"{tool_class.__name__} missing tool_name attribute"
        )
        assert isinstance(tool_class.tool_name, str), (
            f"{tool_class.__name__}.tool_name is not a string"
        )
        # tool_name should be snake_case version of class name
        assert tool_class.tool_name.islower(), (
            f"{tool_class.__name__}.tool_name should be snake_case"
        )
        assert "_" in tool_class.tool_name or len(tool_class.tool_name) <= 4, (
            f"{tool_class.__name__}.tool_name should contain underscores for "
            "multi-word names"
        )


def test_tool_name_consistency():
    """Test that tool_name matches the expected snake_case conversion."""
    expected_names = {
        BashTool: "bash_tool",
        FileEditorTool: "file_editor_tool",
        TaskTrackerTool: "task_tracker_tool",
        BrowserToolSet: "browser_tool_set",
        GrepTool: "grep_tool",
        GlobTool: "glob_tool",
        PlanningFileEditorTool: "planning_file_editor_tool",
    }

    for tool_class, expected_name in expected_names.items():
        assert tool_class.tool_name == expected_name, (
            f"{tool_class.__name__}.tool_name should be '{expected_name}'"
        )


def test_tool_name_accessible_at_class_level():
    """Test that tool_name can be accessed at the class level without instantiation."""
    # This should not raise any errors and should return snake_case names
    assert BashTool.tool_name == "bash_tool"
    assert FileEditorTool.tool_name == "file_editor_tool"
    assert TaskTrackerTool.tool_name == "task_tracker_tool"
    assert BrowserToolSet.tool_name == "browser_tool_set"
    assert GrepTool.tool_name == "grep_tool"
    assert GlobTool.tool_name == "glob_tool"
    assert PlanningFileEditorTool.tool_name == "planning_file_editor_tool"
