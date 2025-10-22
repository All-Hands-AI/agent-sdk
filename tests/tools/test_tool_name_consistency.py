"""Test that tool_name class variables are consistent with registration and usage."""

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
        assert tool_class.tool_name == tool_class.__name__, (
            f"{tool_class.__name__}.tool_name should equal class name"
        )


def test_tool_name_consistency():
    """Test that tool_name matches the expected class name."""
    expected_names = {
        BashTool: "BashTool",
        FileEditorTool: "FileEditorTool",
        TaskTrackerTool: "TaskTrackerTool",
        BrowserToolSet: "BrowserToolSet",
        GrepTool: "GrepTool",
        GlobTool: "GlobTool",
        PlanningFileEditorTool: "PlanningFileEditorTool",
    }

    for tool_class, expected_name in expected_names.items():
        assert tool_class.tool_name == expected_name, (
            f"{tool_class.__name__}.tool_name should be '{expected_name}'"
        )


def test_tool_name_accessible_at_class_level():
    """Test that tool_name can be accessed at the class level without instantiation."""
    # This should not raise any errors
    assert BashTool.tool_name == "BashTool"
    assert FileEditorTool.tool_name == "FileEditorTool"
    assert TaskTrackerTool.tool_name == "TaskTrackerTool"
    assert BrowserToolSet.tool_name == "BrowserToolSet"
    assert GrepTool.tool_name == "GrepTool"
    assert GlobTool.tool_name == "GlobTool"
    assert PlanningFileEditorTool.tool_name == "PlanningFileEditorTool"
