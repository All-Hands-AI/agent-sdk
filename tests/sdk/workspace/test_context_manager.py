"""Tests for workspace context manager support."""

import os

from openhands.sdk.workspace import LocalWorkspace


def test_local_workspace_context_manager() -> None:
    """Test that LocalWorkspace can be used as a context manager."""
    working_dir = os.getcwd()

    with LocalWorkspace(working_dir=working_dir) as workspace:
        assert workspace is not None
        assert workspace.working_dir == working_dir

        # Test that workspace operations work inside context
        result = workspace.execute_command("echo 'test'")
        assert result["exit_code"] == 0
        assert "test" in result["stdout"]


def test_local_workspace_context_manager_with_exception() -> None:
    """Test that LocalWorkspace context manager handles exceptions properly."""
    working_dir = os.getcwd()

    try:
        with LocalWorkspace(working_dir=working_dir) as workspace:
            assert workspace is not None
            # Raise an exception inside the context
            raise ValueError("Test exception")
    except ValueError as e:
        assert str(e) == "Test exception"
        # Context manager should handle cleanup even with exception


def test_local_workspace_without_context_manager() -> None:
    """Test that LocalWorkspace still works without context manager."""
    working_dir = os.getcwd()
    workspace = LocalWorkspace(working_dir=working_dir)

    result = workspace.execute_command("echo 'test'")
    assert result["exit_code"] == 0
    assert "test" in result["stdout"]
