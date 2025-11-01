"""Test automatic tool naming functionality."""


def test_camel_to_snake_conversion():
    """Test the _camel_to_snake utility function."""
    from openhands.sdk.tool.tool import _camel_to_snake

    # Test basic conversions
    assert _camel_to_snake("BashTool") == "bash_tool"
    assert _camel_to_snake("FileEditorTool") == "file_editor_tool"
    assert _camel_to_snake("GrepTool") == "grep_tool"
    assert _camel_to_snake("PlanningFileEditorTool") == "planning_file_editor_tool"
    assert _camel_to_snake("BrowserToolSet") == "browser_tool_set"
    assert _camel_to_snake("TaskTrackerTool") == "task_tracker_tool"
    assert _camel_to_snake("GlobTool") == "glob_tool"

    # Test edge cases
    assert _camel_to_snake("Tool") == "tool"
    assert _camel_to_snake("A") == "a"
    assert _camel_to_snake("AB") == "ab"  # All uppercase, no separation needed
    assert _camel_to_snake("ABC") == "abc"  # All uppercase, no separation needed
    assert _camel_to_snake("XMLParser") == "xml_parser"
    assert _camel_to_snake("HTTPClient") == "http_client"


def test_real_tools_have_correct_names():
    """Test that real tools have the expected automatic names."""
    from openhands.tools.execute_bash import BashTool
    from openhands.tools.file_editor import FileEditorTool
    from openhands.tools.glob import GlobTool
    from openhands.tools.grep import GrepTool
    from openhands.tools.planning_file_editor import PlanningFileEditorTool
    from openhands.tools.task_tracker import TaskTrackerTool

    # Verify all tools have correct automatic names
    assert BashTool.tool_name == "bash_tool"
    assert FileEditorTool.tool_name == "file_editor_tool"
    assert GrepTool.tool_name == "grep_tool"
    assert PlanningFileEditorTool.tool_name == "planning_file_editor_tool"
    assert TaskTrackerTool.tool_name == "task_tracker_tool"
    assert GlobTool.tool_name == "glob_tool"


def test_tool_name_consistency():
    """Test that tool names are consistent across imports."""
    # Import the same tool multiple times to ensure consistency
    from openhands.tools.execute_bash import (
        BashTool as BashTool1,
        BashTool as BashTool2,
    )

    assert BashTool1.tool_name == BashTool2.tool_name == "bash_tool"

    # Test with different tools
    from openhands.tools.file_editor import FileEditorTool
    from openhands.tools.grep import GrepTool

    assert FileEditorTool.tool_name == "file_editor_tool"
    assert GrepTool.tool_name == "grep_tool"
    assert FileEditorTool.tool_name != GrepTool.tool_name
