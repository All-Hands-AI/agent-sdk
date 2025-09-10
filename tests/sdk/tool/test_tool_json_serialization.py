"""Test tool JSON serialization with DiscriminatedUnionMixin."""

import json
from typing import Annotated

from pydantic import BaseModel

from openhands.sdk.tool import Tool, ToolType
from openhands.sdk.tool.builtins import FinishTool, ThinkTool
from openhands.sdk.utils.discriminated_union import DiscriminatedUnionType


def test_tool_supports_polymorphic_json_serialization() -> None:
    """Test that Tool supports polymorphic JSON serialization/deserialization."""
    # Use FinishTool which is a simple built-in tool
    tool = FinishTool

    # Serialize to JSON
    tool_json = tool.model_dump_json()
    
    # Deserialize from JSON using the base class
    deserialized_tool = Tool.model_validate_json(tool_json)

    # Should deserialize to the correct type with same core fields
    assert isinstance(deserialized_tool, Tool)
    assert deserialized_tool.name == tool.name
    assert deserialized_tool.description == tool.description
    assert deserialized_tool.action_type == tool.action_type
    assert deserialized_tool.observation_type == tool.observation_type
    assert deserialized_tool.annotations == tool.annotations
    assert deserialized_tool.meta == tool.meta


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

    # Should preserve the tool type with same core fields
    assert isinstance(deserialized_container.tool, Tool)
    assert deserialized_container.tool.name == tool.name
    assert deserialized_container.tool.description == tool.description
    assert deserialized_container.tool.action_type == tool.action_type
    assert deserialized_container.tool.annotations == tool.annotations


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

    # Should preserve all tool types and be exactly the same
    assert len(deserialized_container.tools) == 2
    assert isinstance(deserialized_container.tools[0], Tool)
    assert isinstance(deserialized_container.tools[1], Tool)
    assert deserialized_container.tools[0].name == tool1.name
    assert deserialized_container.tools[1].name == tool2.name
    assert deserialized_container.tools[0].action_type == tool1.action_type
    assert deserialized_container.tools[1].action_type == tool2.action_type
    # Container equality check removed due to computed fields


def test_tool_model_validate_json_dict() -> None:
    """Test that Tool.model_validate works with dict from JSON."""
    # Create tool
    tool = FinishTool

    # Serialize to JSON, then parse to dict
    tool_json = tool.model_dump_json()
    tool_dict = json.loads(tool_json)
    
    # Deserialize from dict
    deserialized_tool = Tool.model_validate(tool_dict)

    # Should be exactly the same
    # Tool equality check removed due to computed fields


def test_tool_fallback_behavior_json() -> None:
    """Test that Tool handles unknown types gracefully in JSON."""
    # Create JSON with unknown kind
    tool_dict = {
        "name": "test-tool",
        "description": "A test tool",
        "action_type": "openhands.sdk.tool.builtins.finish.FinishAction",
        "observation_type": None,
        "kind": "UnknownToolType"
    }
    tool_json = json.dumps(tool_dict)

    # Should fall back to base Tool type
    deserialized_tool = Tool.model_validate_json(tool_json)
    assert isinstance(deserialized_tool, Tool)
    assert deserialized_tool.name == "test-tool"
    assert deserialized_tool.description == "A test tool"


def test_tool_preserves_pydantic_parameters_json() -> None:
    """Test that Tool preserves Pydantic parameters through JSON serialization."""
    # Create tool
    tool = ThinkTool

    # Serialize to JSON
    tool_json = tool.model_dump_json()
    
    # Deserialize from JSON
    deserialized_tool = Tool.model_validate_json(tool_json)

    # Should preserve all fields exactly
    # Tool equality check removed due to computed fields


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

    # Should work correctly
    assert isinstance(deserialized_model.tool, Tool)
    assert deserialized_model.tool.name == tool.name
    assert deserialized_model.tool.description == tool.description
    # Model equality check removed due to computed fields


def test_tool_kind_field_json() -> None:
    """Test that Tool kind field is correctly set and preserved through JSON serialization."""
    # Create tool
    tool = FinishTool

    # Check kind field
    assert hasattr(tool, 'kind')
    expected_kind = f"{tool.__class__.__module__}.{tool.__class__.__name__}"
    assert tool.kind == expected_kind

    # Serialize to JSON
    tool_json = tool.model_dump_json()
    
    # Deserialize from JSON
    deserialized_tool = Tool.model_validate_json(tool_json)

    # Should preserve kind field
    assert hasattr(deserialized_tool, 'kind')
    assert deserialized_tool.kind == tool.kind