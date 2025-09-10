"""Test tool serialization with DiscriminatedUnionMixin."""

from typing import Annotated

import pytest
from pydantic import BaseModel, Field

from openhands.sdk.tool import Tool, ToolType
from openhands.sdk.tool.builtins import FinishTool, ThinkTool
from openhands.sdk.tool.schema import ActionBase, ObservationBase
from openhands.sdk.utils.discriminated_union import DiscriminatedUnionType
from openhands.tools.execute_bash.definition import BashTool


def test_tool_supports_polymorphic_deserialization() -> None:
    """Test that Tool supports polymorphic deserialization from dict data."""
    # Use FinishTool as a concrete Tool instance
    tool = FinishTool

    # Get the serialized data as dict (not JSON due to non-serializable fields)
    tool_data = tool.model_dump()

    # Deserialize using the base class
    deserialized_tool = Tool.model_validate(tool_data)

    # Should deserialize to the correct concrete type
    assert type(deserialized_tool) == type(tool)
    assert deserialized_tool.name == tool.name
    assert deserialized_tool.description == tool.description
    assert deserialized_tool.action_type == tool.action_type
    assert deserialized_tool.observation_type == tool.observation_type


def test_tool_supports_polymorphic_field_deserialization() -> None:
    """Test that Tool supports polymorphic deserialization when used as a field."""

    class ToolContainer(BaseModel):
        tool: Annotated[Tool, DiscriminatedUnionType[Tool]]

    # Use ThinkTool as a concrete Tool instance
    tool = ThinkTool
    container = ToolContainer(tool=tool)

    # Get dict data (not JSON due to non-serializable fields)
    container_data = container.model_dump()
    deserialized_container = ToolContainer.model_validate(container_data)

    # Should deserialize to the correct concrete type
    assert type(deserialized_container.tool) == type(tool)
    assert deserialized_container.tool.name == tool.name
    assert deserialized_container.tool.description == tool.description


def test_tool_supports_nested_polymorphic_deserialization() -> None:
    """Test that Tool supports polymorphic deserialization when nested in lists."""

    class ToolRegistry(BaseModel):
        tools: list[Annotated[Tool, DiscriminatedUnionType[Tool]]]

    # Use built-in tools as concrete Tool instances
    tools = [FinishTool, ThinkTool]
    registry = ToolRegistry(tools=tools)

    # Get dict data (not JSON due to non-serializable fields)
    registry_data = registry.model_dump()
    deserialized_registry = ToolRegistry.model_validate(registry_data)

    # Should deserialize to the correct concrete types
    assert len(deserialized_registry.tools) == 2
    assert type(deserialized_registry.tools[0]) == type(FinishTool)
    assert type(deserialized_registry.tools[1]) == type(ThinkTool)
    assert deserialized_registry.tools[0].name == "finish"
    assert deserialized_registry.tools[1].name == "think"


def test_tool_model_validate_dict() -> None:
    """Test Tool model_validate with dictionary input."""
    # Use FinishTool as a concrete Tool instance
    tool = FinishTool
    tool_data = tool.model_dump()

    # Test with valid kind
    result = Tool.model_validate(tool_data)
    assert type(result) == type(tool)
    assert result.name == tool.name
    assert result.description == tool.description
    assert result.action_type == tool.action_type
    assert result.observation_type == tool.observation_type


def test_tool_fallback_behavior() -> None:
    """Test fallback behavior when discriminated union logic doesn't apply."""

    # Create a minimal tool data without kind
    class TestAction(ActionBase):
        test_field: str = Field(description="Test field")

    class TestObservation(ObservationBase):
        result: str = Field(description="Test result")

    no_kind_data = {
        "name": "test_tool",
        "description": "A test tool",
        "action_type": TestAction,
        "observation_type": TestObservation,
    }

    # Test with missing kind - should fallback to base class
    result = Tool.model_validate(no_kind_data)
    assert isinstance(result, Tool)
    assert result.name == "test_tool"

    # Test with invalid kind - should fallback to base class
    invalid_kind_data = {**no_kind_data, "kind": "InvalidTool"}
    result = Tool.model_validate(invalid_kind_data)
    assert isinstance(result, Tool)
    assert result.name == "test_tool"


def test_tool_preserves_pydantic_parameters() -> None:
    """Test that all Pydantic validation parameters are preserved."""
    tool = FinishTool
    tool_data = tool.model_dump()

    # Test with strict mode
    result = Tool.model_validate(tool_data, strict=True)
    assert type(result) == type(tool)

    # Test with context (even though we don't use it here, it should be passed through)
    context = {"test": "value"}
    result = Tool.model_validate(tool_data, context=context)
    assert type(result) == type(tool)


def test_tool_type_annotation_works() -> None:
    """Test that ToolType annotation works correctly."""

    class ToolWrapper(BaseModel):
        tool: ToolType

    tool = ThinkTool
    wrapper = ToolWrapper(tool=tool)

    # Get dict data (not JSON due to non-serializable fields)
    wrapper_data = wrapper.model_dump()
    deserialized_wrapper = ToolWrapper.model_validate(wrapper_data)

    # Should deserialize to the correct concrete type
    assert type(deserialized_wrapper.tool) == type(tool)
    assert deserialized_wrapper.tool.name == tool.name


def test_custom_tool_subclass_deserialization() -> None:
    """Test that custom Tool subclasses deserialize correctly."""

    # Create a BashTool instance (which is a Tool subclass)
    bash_tool = BashTool.create(working_dir="/tmp")

    # Get dict data (not JSON due to non-serializable fields)
    tool_data = bash_tool.model_dump()
    deserialized_tool = Tool.model_validate(tool_data)

    # Should deserialize to the correct concrete type
    assert isinstance(deserialized_tool, BashTool)
    assert deserialized_tool.name == bash_tool.name
    assert deserialized_tool.description == bash_tool.description
    assert deserialized_tool.action_type == bash_tool.action_type
    assert deserialized_tool.observation_type == bash_tool.observation_type


def test_tool_with_annotations_deserialization() -> None:
    """Test that Tool with annotations deserializes correctly."""
    # FinishTool has annotations
    tool = FinishTool

    # Get dict data (not JSON due to non-serializable fields)
    tool_data = tool.model_dump()
    deserialized_tool = Tool.model_validate(tool_data)

    # Should preserve annotations
    assert deserialized_tool.annotations == tool.annotations
    assert deserialized_tool.annotations.readOnlyHint == tool.annotations.readOnlyHint
    assert deserialized_tool.annotations.destructiveHint == tool.annotations.destructiveHint
    assert deserialized_tool.annotations.idempotentHint == tool.annotations.idempotentHint
    assert deserialized_tool.annotations.openWorldHint == tool.annotations.openWorldHint