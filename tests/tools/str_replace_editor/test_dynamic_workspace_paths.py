"""Tests for dynamic workspace path functionality in FileEditorTool."""

import os
import tempfile

from openhands.tools import FileEditorTool
from openhands.tools.str_replace_editor import (
    StrReplaceEditorAction,
    StrReplaceEditorObservation,
)


def test_file_editor_tool_default_workspace_path():
    """Test that FileEditorTool uses default /workspace path when no workspace_root is provided."""  # noqa: E501
    tool = FileEditorTool.create()

    # Check that the action type has the default path description
    path_field = tool.action_type.model_fields["path"]
    assert path_field.description is not None
    assert "/workspace/file.py" in path_field.description
    assert "/workspace`." in path_field.description


def test_file_editor_tool_custom_workspace_path():
    """Test that FileEditorTool uses custom workspace path when workspace_root is provided."""  # noqa: E501
    custom_workspace = "/custom/workspace"
    tool = FileEditorTool.create(workspace_root=custom_workspace)

    # Check that the action type has the custom path description
    path_field = tool.action_type.model_fields["path"]
    assert path_field.description is not None
    assert f"{custom_workspace}/file.py" in path_field.description
    assert f"{custom_workspace}`." in path_field.description

    # Ensure it doesn't contain the default path (check for exact match with backtick)
    assert "`/workspace/file.py`" not in path_field.description


def test_file_editor_tool_workspace_path_in_examples():
    """Test that workspace path appears in path field description examples."""
    custom_workspace = "/app"
    tool = FileEditorTool.create(workspace_root=custom_workspace)

    # Verify that the path field description is updated
    path_field = tool.action_type.model_fields["path"]
    assert path_field.description is not None
    assert "/app/file.py" in path_field.description
    assert "/app`." in path_field.description

    # Ensure it doesn't contain the default path (check for exact match with backtick)
    assert "`/workspace/file.py`" not in path_field.description


def test_file_editor_tool_functional_with_custom_workspace():
    """Test that FileEditorTool functions correctly with custom workspace path."""
    with tempfile.TemporaryDirectory() as temp_dir:
        tool = FileEditorTool.create(workspace_root=temp_dir)

        test_file = os.path.join(temp_dir, "test.txt")

        # Create a file using the tool
        action = StrReplaceEditorAction(
            command="create",
            path=test_file,
            file_text="Hello, Custom Workspace!",
            security_risk="LOW",
        )

        result = tool.call(action)

        # Check that the operation succeeded
        assert result is not None
        assert isinstance(result, StrReplaceEditorObservation)
        assert not result.error
        assert os.path.exists(test_file)

        # Check file contents
        with open(test_file, "r") as f:
            content = f.read()
        assert content == "Hello, Custom Workspace!"


def test_file_editor_tool_different_workspace_paths():
    """Test that different workspace paths create different path field descriptions."""
    workspace1 = "/workspace1"
    workspace2 = "/workspace2"

    tool1 = FileEditorTool.create(workspace_root=workspace1)
    tool2 = FileEditorTool.create(workspace_root=workspace2)

    # Check path field descriptions
    path_field1 = tool1.action_type.model_fields["path"]
    path_field2 = tool2.action_type.model_fields["path"]

    assert path_field1.description is not None
    assert path_field2.description is not None
    assert f"{workspace1}/file.py" in path_field1.description
    assert f"{workspace2}/file.py" in path_field2.description

    # Check that they don't contain each other's paths (check for exact match with backtick)  # noqa: E501
    assert f"`{workspace2}/file.py`" not in path_field1.description
    assert f"`{workspace1}/file.py`" not in path_field2.description


def test_file_editor_tool_none_workspace_root():
    """Test that None workspace_root falls back to default behavior."""
    tool = FileEditorTool.create(workspace_root=None)

    # Should behave the same as not providing workspace_root
    path_field = tool.action_type.model_fields["path"]
    assert path_field.description is not None
    assert "/workspace/file.py" in path_field.description
    assert "/workspace`." in path_field.description
