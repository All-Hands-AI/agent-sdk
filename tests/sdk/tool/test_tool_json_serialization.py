"""Test tool JSON serialization with DiscriminatedUnionMixin."""

import json

from pydantic import BaseModel

from openhands.sdk.tool import Tool, ToolType
from openhands.sdk.tool.builtins import FinishTool, ThinkTool


def test_tool_serialization_deserialization() -> None:
    """Test that Tool supports polymorphic JSON serialization/deserialization."""
    # Use FinishTool which is a simple built-in tool
    tool = FinishTool

    # Serialize to JSON
    tool_json = tool.model_dump_json()

    # Deserialize from JSON using the base class
    deserialized_tool = Tool.model_validate_json(tool_json)

    # Should deserialize to the correct type with same serializable data
    assert isinstance(deserialized_tool, Tool)
    assert tool.model_dump() == deserialized_tool.model_dump()


def test_tool_supports_polymorphic_field_json_serialization() -> None:
    """Test that Tool supports polymorphic JSON serialization when used as a field."""

    class Container(BaseModel):
        tool: Tool

    # Create container with tool
    tool = FinishTool
    container = Container(tool=tool)

    # Serialize to JSON
    container_json = container.model_dump_json()

    # Deserialize from JSON
    deserialized_container = Container.model_validate_json(container_json)

    # Should preserve the tool type with same serializable data
    assert isinstance(deserialized_container.tool, Tool)
    assert tool.model_dump() == deserialized_container.tool.model_dump()


def test_tool_supports_nested_polymorphic_json_serialization() -> None:
    """Test that Tool supports nested polymorphic JSON serialization."""

    class NestedContainer(BaseModel):
        tools: list[Tool]

    # Create container with multiple tools
    tool1 = FinishTool
    tool2 = ThinkTool
    container = NestedContainer(tools=[tool1, tool2])

    # Serialize to JSON
    container_json = container.model_dump_json()

    # Deserialize from JSON
    deserialized_container = NestedContainer.model_validate_json(container_json)

    # Should preserve all tool types with same serializable data
    assert len(deserialized_container.tools) == 2
    assert isinstance(deserialized_container.tools[0], Tool)
    assert isinstance(deserialized_container.tools[1], Tool)
    assert tool1.model_dump() == deserialized_container.tools[0].model_dump()
    assert tool2.model_dump() == deserialized_container.tools[1].model_dump()


def test_tool_model_validate_json_dict() -> None:
    """Test that Tool.model_validate works with dict from JSON."""
    # Create tool
    tool = FinishTool

    # Serialize to JSON, then parse to dict
    tool_json = tool.model_dump_json()
    tool_dict = json.loads(tool_json)

    # Deserialize from dict
    deserialized_tool = Tool.model_validate(tool_dict)

    # Should have same serializable data
    assert isinstance(deserialized_tool, Tool)
    assert tool.model_dump() == deserialized_tool.model_dump()


def test_tool_fallback_behavior_json() -> None:
    """Test that Tool handles unknown types gracefully in JSON."""
    # Create JSON with unknown kind
    tool_dict = {
        "name": "test-tool",
        "description": "A test tool",
        "action_type": "openhands.sdk.tool.builtins.finish.FinishAction",
        "observation_type": None,
        "kind": "UnknownToolType",
    }
    tool_json = json.dumps(tool_dict)

    # Should fall back to base Tool type
    deserialized_tool = Tool.model_validate_json(tool_json)
    assert isinstance(deserialized_tool, Tool)
    assert deserialized_tool.name == "test-tool"
    assert deserialized_tool.description == "A test tool"


def test_tool_type_annotation_works_json() -> None:
    """Test that ToolType annotation works correctly with JSON."""
    # Create tool
    tool = FinishTool

    # Use ToolType annotation
    class TestModel(BaseModel):
        tool: ToolType

    model = TestModel(tool=tool)

    # Serialize to JSON
    model_json = model.model_dump_json()

    # Deserialize from JSON
    deserialized_model = TestModel.model_validate_json(model_json)

    # Should work correctly with same serializable data
    assert isinstance(deserialized_model.tool, Tool)
    assert tool.model_dump() == deserialized_model.tool.model_dump()


def test_tool_kind_field_json() -> None:
    """Test Tool kind field is correctly set and preserved through JSON."""
    # Create tool
    tool = FinishTool

    # Check kind field
    assert hasattr(tool, "kind")
    expected_kind = f"{tool.__class__.__module__}.{tool.__class__.__name__}"
    assert tool.kind == expected_kind

    # Serialize to JSON
    tool_json = tool.model_dump_json()

    # Deserialize from JSON
    deserialized_tool = Tool.model_validate_json(tool_json)

    # Should preserve kind field
    assert hasattr(deserialized_tool, "kind")
    assert deserialized_tool.kind == tool.kind
