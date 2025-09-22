"""Test ToolSpec class functionality."""

import pytest
from pydantic import ValidationError

from openhands.sdk.tool.spec import ToolSpec


def test_tool_spec_minimal():
    """Test creating ToolSpec with minimal required fields."""
    spec = ToolSpec(name="TestTool")

    assert spec.name == "TestTool"
    assert spec.params == {}


def test_tool_spec_with_params():
    """Test creating ToolSpec with parameters."""
    params = {"working_dir": "/workspace", "timeout": 30}
    spec = ToolSpec(name="TestTool", params=params)

    assert spec.name == "TestTool"
    assert spec.params == params


def test_tool_spec_complex_params():
    """Test creating ToolSpec with complex parameters."""
    params = {
        "working_dir": "/workspace",
        "env_vars": {"PATH": "/usr/bin", "HOME": "/home/user"},
        "timeout": 60,
        "shell": "/bin/bash",
        "debug": True,
    }

    spec = ToolSpec(name="TestTool", params=params)

    assert spec.name == "TestTool"
    assert spec.params == params
    assert spec.params["env_vars"]["PATH"] == "/usr/bin"
    assert spec.params["debug"] is True


def test_tool_spec_serialization():
    """Test ToolSpec serialization and deserialization."""
    params = {"working_dir": "/test", "timeout": 45}
    spec = ToolSpec(name="TestTool", params=params)

    # Test model_dump
    spec_dict = spec.model_dump()
    assert spec_dict["name"] == "TestTool"
    assert spec_dict["params"] == params

    # Test model_dump_json
    spec_json = spec.model_dump_json()
    assert isinstance(spec_json, str)

    # Test deserialization
    spec_restored = ToolSpec.model_validate_json(spec_json)
    assert spec_restored.name == "TestTool"
    assert spec_restored.params == params


def test_tool_spec_validation_requires_name():
    """Test that ToolSpec requires a name."""
    with pytest.raises(ValidationError):
        ToolSpec()  # type: ignore


def test_tool_spec_examples_from_docstring():
    """Test the examples provided in ToolSpec docstring."""
    # Test the examples from the docstring
    examples = ["TestTool", "AnotherTool", "TaskTrackerTool"]

    for example_name in examples:
        spec = ToolSpec(name=example_name)
        assert spec.name == example_name
        assert spec.params == {}

    # Test with params example
    spec_with_params = ToolSpec(name="TestTool", params={"working_dir": "/workspace"})
    assert spec_with_params.name == "TestTool"
    assert spec_with_params.params == {"working_dir": "/workspace"}


def test_tool_spec_different_tool_types():
    """Test creating ToolSpec for different tool types."""
    # TestTool
    test_spec = ToolSpec(
        name="TestTool", params={"working_dir": "/workspace", "timeout": 30}
    )
    assert test_spec.name == "TestTool"
    assert test_spec.params["working_dir"] == "/workspace"

    # AnotherTool
    another_spec = ToolSpec(name="AnotherTool")
    assert another_spec.name == "AnotherTool"
    assert another_spec.params == {}

    # TaskTrackerTool
    tracker_spec = ToolSpec(
        name="TaskTrackerTool", params={"save_dir": "/workspace/.openhands"}
    )
    assert tracker_spec.name == "TaskTrackerTool"
    assert tracker_spec.params["save_dir"] == "/workspace/.openhands"


def test_tool_spec_nested_params():
    """Test ToolSpec with nested parameter structures."""
    params = {
        "config": {
            "timeout": 30,
            "retries": 3,
            "options": {"verbose": True, "debug": False},
        },
        "paths": ["/usr/bin", "/usr/local/bin"],
        "env": {"LANG": "en_US.UTF-8"},
    }

    spec = ToolSpec(name="ComplexTool", params=params)

    assert spec.name == "ComplexTool"
    assert spec.params["config"]["timeout"] == 30
    assert spec.params["config"]["options"]["verbose"] is True
    assert spec.params["paths"] == ["/usr/bin", "/usr/local/bin"]
    assert spec.params["env"]["LANG"] == "en_US.UTF-8"


def test_tool_spec_field_descriptions():
    """Test that ToolSpec fields have proper descriptions."""
    fields = ToolSpec.model_fields

    assert "name" in fields
    assert fields["name"].description is not None
    assert "Name of the tool class" in fields["name"].description
    assert (
        "Import it from an `openhands.tools.<module>` subpackage."
        in fields["name"].description
    )

    assert "params" in fields
    assert fields["params"].description is not None
    assert "Parameters for the tool's .create() method" in fields["params"].description


def test_tool_spec_default_params():
    """Test that ToolSpec has correct default for params."""
    spec = ToolSpec(name="TestTool")
    assert spec.params == {}


def test_tool_spec_immutability():
    """Test that ToolSpec behaves correctly with parameter modifications."""
    original_params = {"working_dir": "/workspace"}
    spec = ToolSpec(name="BashTool", params=original_params)

    # Modifying the original params should not affect the spec
    original_params["working_dir"] = "/changed"
    assert spec.params["working_dir"] == "/workspace"


def test_tool_spec_validation_edge_cases():
    """Test ToolSpec validation with edge cases."""
    # Empty string name should be invalid
    with pytest.raises(ValidationError):
        ToolSpec(name="")

    # None params should use default empty dict (handled by validator)
    spec = ToolSpec(name="TestTool")
    assert spec.params == {}


def test_tool_spec_repr():
    """Test ToolSpec string representation."""
    spec = ToolSpec(name="BashTool", params={"working_dir": "/test"})
    repr_str = repr(spec)

    assert "ToolSpec" in repr_str
    assert "BashTool" in repr_str
