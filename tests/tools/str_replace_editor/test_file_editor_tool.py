"""Tests for FileEditorTool subclass."""

import os
import tempfile
from unittest.mock import patch

from openhands.tools import FileEditorTool
from openhands.tools.str_replace_editor import (
    StrReplaceEditorAction,
    StrReplaceEditorObservation,
)
from openhands.tools.str_replace_editor.definition import (
    _get_workspace_mount_path_from_env,
)


def test_file_editor_tool_initialization():
    """Test that FileEditorTool initializes correctly."""
    tool = FileEditorTool.create()

    # Check that the tool has the correct name and properties
    assert tool.name == "str_replace_editor"
    assert tool.executor is not None
    # The action type is now dynamic, but should be a subclass of StrReplaceEditorAction
    assert issubclass(tool.action_type, StrReplaceEditorAction)


def test_file_editor_tool_create_file():
    """Test that FileEditorTool can create files."""
    tool = FileEditorTool.create()

    with tempfile.TemporaryDirectory() as temp_dir:
        test_file = os.path.join(temp_dir, "test.txt")

        # Create an action to create a file
        action = StrReplaceEditorAction(
            command="create",
            path=test_file,
            file_text="Hello, World!",
            security_risk="LOW",
        )

        # Execute the action
        result = tool.call(action)

        # Check the result
        assert result is not None
        assert isinstance(result, StrReplaceEditorObservation)
        assert not result.error
        assert os.path.exists(test_file)

        # Check file contents
        with open(test_file, "r") as f:
            content = f.read()
        assert content == "Hello, World!"


def test_file_editor_tool_view_file():
    """Test that FileEditorTool can view files."""
    tool = FileEditorTool.create()

    with tempfile.TemporaryDirectory() as temp_dir:
        test_file = os.path.join(temp_dir, "test.txt")

        # Create a test file
        with open(test_file, "w") as f:
            f.write("Line 1\nLine 2\nLine 3")

        # Create an action to view the file
        action = StrReplaceEditorAction(
            command="view", path=test_file, security_risk="LOW"
        )

        # Execute the action
        result = tool.call(action)

        # Check the result
        assert result is not None
        assert isinstance(result, StrReplaceEditorObservation)
        assert not result.error
        assert "Line 1" in result.output
        assert "Line 2" in result.output
        assert "Line 3" in result.output


def test_file_editor_tool_str_replace():
    """Test that FileEditorTool can perform string replacement."""
    tool = FileEditorTool.create()

    with tempfile.TemporaryDirectory() as temp_dir:
        test_file = os.path.join(temp_dir, "test.txt")

        # Create a test file
        with open(test_file, "w") as f:
            f.write("Hello, World!\nThis is a test.")

        # Create an action to replace text
        action = StrReplaceEditorAction(
            command="str_replace",
            path=test_file,
            old_str="World",
            new_str="Universe",
            security_risk="LOW",
        )

        # Execute the action
        result = tool.call(action)

        # Check the result
        assert result is not None
        assert isinstance(result, StrReplaceEditorObservation)
        assert not result.error

        # Check file contents
        with open(test_file, "r") as f:
            content = f.read()
        assert "Hello, Universe!" in content


def test_file_editor_tool_to_openai_tool():
    """Test that FileEditorTool can be converted to OpenAI tool format."""
    tool = FileEditorTool.create()

    # Convert to OpenAI tool format
    openai_tool = tool.to_openai_tool()

    # Check the format
    assert openai_tool["type"] == "function"
    assert openai_tool["function"]["name"] == "str_replace_editor"
    assert "description" in openai_tool["function"]
    assert "parameters" in openai_tool["function"]


def test_file_editor_tool_view_directory():
    """Test that FileEditorTool can view directories."""
    tool = FileEditorTool.create()

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create some test files
        test_file1 = os.path.join(temp_dir, "file1.txt")
        test_file2 = os.path.join(temp_dir, "file2.txt")

        with open(test_file1, "w") as f:
            f.write("File 1 content")
        with open(test_file2, "w") as f:
            f.write("File 2 content")

        # Create an action to view the directory
        action = StrReplaceEditorAction(
            command="view", path=temp_dir, security_risk="LOW"
        )

        # Execute the action
        result = tool.call(action)

        # Check the result
        assert result is not None
        assert isinstance(result, StrReplaceEditorObservation)
        assert not result.error
        assert "file1.txt" in result.output
        assert "file2.txt" in result.output


def test_workspace_path_detection_docker_runtime():
    """Test that DockerRuntime ignores SANDBOX_VOLUMES and uses /workspace."""
    with patch.dict(os.environ, {"SANDBOX_VOLUMES": "/host/app:/workspace:rw"}):
        result = _get_workspace_mount_path_from_env(runtime_type="docker")
        assert result == "/workspace"


def test_workspace_path_detection_local_runtime():
    """Test that LocalRuntime uses host path from SANDBOX_VOLUMES."""
    with patch.dict(os.environ, {"SANDBOX_VOLUMES": "/host/app:/workspace:rw"}):
        result = _get_workspace_mount_path_from_env(runtime_type="local")
        assert result == "/host/app"


def test_workspace_path_detection_local_runtime_multiple_mounts():
    """Test LocalRuntime with multiple mounts, finds /workspace mount."""
    sandbox_volumes = "/tmp:/tmp:rw,/home/user/project:/workspace:rw,/var:/var:rw"
    with patch.dict(
        os.environ,
        {"SANDBOX_VOLUMES": sandbox_volumes},
    ):
        result = _get_workspace_mount_path_from_env(runtime_type="local")
        assert result == "/home/user/project"


def test_workspace_path_detection_local_runtime_no_workspace_mount():
    """Test LocalRuntime with no /workspace mount falls back to current directory."""
    with patch.dict(os.environ, {"SANDBOX_VOLUMES": "/tmp:/tmp:rw,/var:/var:rw"}):
        result = _get_workspace_mount_path_from_env(runtime_type="local")
        assert result == os.getcwd()


def test_workspace_path_detection_local_runtime_no_sandbox_volumes():
    """Test LocalRuntime with no SANDBOX_VOLUMES falls back to current directory."""
    with patch.dict(os.environ, {}, clear=True):
        result = _get_workspace_mount_path_from_env(runtime_type="local")
        assert result == os.getcwd()


def test_file_editor_tool_dynamic_workspace_path_docker():
    """Test FileEditorTool with DockerRuntime shows /workspace in description."""
    with patch.dict(os.environ, {"SANDBOX_VOLUMES": "/host/app:/workspace:rw"}):
        tool = FileEditorTool.create(runtime_type="docker")
        openai_tool = tool.to_openai_tool()
        assert "parameters" in openai_tool["function"]
        path_description = openai_tool["function"]["parameters"]["properties"]["path"][
            "description"
        ]
        assert "/workspace/file.py" in path_description
        assert "/workspace`." in path_description
        # Should not contain host paths
        assert "/host/app" not in path_description


def test_file_editor_tool_dynamic_workspace_path_local():
    """Test FileEditorTool with LocalRuntime shows host path in description."""
    with patch.dict(os.environ, {"SANDBOX_VOLUMES": "/host/app:/workspace:rw"}):
        tool = FileEditorTool.create(runtime_type="local")
        openai_tool = tool.to_openai_tool()
        assert "parameters" in openai_tool["function"]
        path_description = openai_tool["function"]["parameters"]["properties"]["path"][
            "description"
        ]
        assert "/host/app/file.py" in path_description
        assert "/host/app`." in path_description


def test_file_editor_tool_explicit_workspace_path():
    """Test FileEditorTool with explicitly provided workspace path."""
    tool = FileEditorTool.create(workspace_mount_path_in_sandbox="/custom/path")
    openai_tool = tool.to_openai_tool()
    assert "parameters" in openai_tool["function"]
    path_description = openai_tool["function"]["parameters"]["properties"]["path"][
        "description"
    ]
    assert "/custom/path/file.py" in path_description
    assert "/custom/path`." in path_description
