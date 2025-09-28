"""Tests for ToolSpec.resolve_diff_from_deserialized method."""

import pytest

from openhands.sdk.tool.spec import ToolSpec


def test_resolve_diff_from_deserialized_basic():
    """Test basic tool reconciliation with directory parameter override."""
    runtime_tool = ToolSpec(
        name="bash", params={"working_dir": "/runtime/path", "timeout": 30}
    )

    persisted_tool = ToolSpec(
        name="bash", params={"working_dir": "/persisted/path", "timeout": 30}
    )

    reconciled = runtime_tool.resolve_diff_from_deserialized(persisted_tool)

    # Should use runtime working_dir but persisted timeout
    assert reconciled.name == "bash"
    assert reconciled.params["working_dir"] == "/runtime/path"
    assert reconciled.params["timeout"] == 30


def test_resolve_diff_from_deserialized_all_overridable_params():
    """Test reconciliation with all overridable directory parameters."""
    runtime_tool = ToolSpec(
        name="file_editor",
        params={
            "working_dir": "/runtime/work",
            "persistent_dir": "/runtime/persist",
            "save_dir": "/runtime/save",
            "workspace_root": "/runtime/workspace",
            "max_file_size": 1000,
        },
    )

    persisted_tool = ToolSpec(
        name="file_editor",
        params={
            "working_dir": "/persisted/work",
            "persistent_dir": "/persisted/persist",
            "save_dir": "/persisted/save",
            "workspace_root": "/persisted/workspace",
            "max_file_size": 1000,
        },
    )

    reconciled = runtime_tool.resolve_diff_from_deserialized(persisted_tool)

    # All directory params should come from runtime
    assert reconciled.params["working_dir"] == "/runtime/work"
    assert reconciled.params["persistent_dir"] == "/runtime/persist"
    assert reconciled.params["save_dir"] == "/runtime/save"
    assert reconciled.params["workspace_root"] == "/runtime/workspace"
    # Non-directory param should match
    assert reconciled.params["max_file_size"] == 1000


def test_resolve_diff_from_deserialized_different_names_fails():
    """Test that tools with different names cannot be reconciled."""
    runtime_tool = ToolSpec(name="bash", params={})
    persisted_tool = ToolSpec(name="file_editor", params={})

    with pytest.raises(
        ValueError,
        match="Cannot resolve_diff_from_deserialized between tools with different",
    ):
        runtime_tool.resolve_diff_from_deserialized(persisted_tool)


def test_resolve_diff_from_deserialized_non_overridable_param_mismatch_fails():
    """Test that mismatched non-overridable parameters cause failure."""
    runtime_tool = ToolSpec(
        name="bash", params={"working_dir": "/runtime", "timeout": 30}
    )

    persisted_tool = ToolSpec(
        name="bash",
        params={"working_dir": "/persisted", "timeout": 60},  # Different timeout
    )

    with pytest.raises(
        ValueError, match="Tool 'bash' parameter 'timeout' doesn't match"
    ):
        runtime_tool.resolve_diff_from_deserialized(persisted_tool)


def test_resolve_diff_from_deserialized_extra_runtime_param_fails():
    """Test that extra non-overridable parameters in runtime tool cause failure."""
    runtime_tool = ToolSpec(
        name="bash",
        params={"working_dir": "/runtime", "timeout": 30, "extra_param": "value"},
    )

    persisted_tool = ToolSpec(
        name="bash", params={"working_dir": "/persisted", "timeout": 30}
    )

    with pytest.raises(
        ValueError, match="Tool 'bash' has extra parameter 'extra_param'"
    ):
        runtime_tool.resolve_diff_from_deserialized(persisted_tool)


def test_resolve_diff_from_deserialized_missing_overridable_param():
    """Test reconciliation when runtime tool is missing an overridable parameter."""
    runtime_tool = ToolSpec(
        name="bash",
        params={"timeout": 30},  # No working_dir
    )

    persisted_tool = ToolSpec(
        name="bash", params={"working_dir": "/persisted", "timeout": 30}
    )

    reconciled = runtime_tool.resolve_diff_from_deserialized(persisted_tool)

    # Should keep persisted working_dir since runtime doesn't have it
    assert reconciled.params["working_dir"] == "/persisted"
    assert reconciled.params["timeout"] == 30


def test_resolve_diff_from_deserialized_empty_params():
    """Test reconciliation with empty parameters."""
    runtime_tool = ToolSpec(name="simple_tool", params={})
    persisted_tool = ToolSpec(name="simple_tool", params={})

    reconciled = runtime_tool.resolve_diff_from_deserialized(persisted_tool)

    assert reconciled.name == "simple_tool"
    assert reconciled.params == {}


def test_resolve_diff_from_deserialized_verification_failure():
    """Test that verification catches reconciliation issues."""
    # This is a bit contrived, but tests the verification logic
    runtime_tool = ToolSpec(
        name="test_tool", params={"working_dir": "/runtime", "param1": "value1"}
    )

    persisted_tool = ToolSpec(
        name="test_tool", params={"working_dir": "/persisted", "param1": "value1"}
    )

    # This should work normally
    reconciled = runtime_tool.resolve_diff_from_deserialized(persisted_tool)
    assert reconciled.params["working_dir"] == "/runtime"
    assert reconciled.params["param1"] == "value1"
