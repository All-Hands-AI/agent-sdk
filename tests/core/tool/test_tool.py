"""Tests for the Tool class in openhands.core.runtime.tool."""

from typing import Any, Dict, List, Optional

import pytest
from pydantic import Field

from openhands.core.tool import (
    ActionBase,
    ObservationBase,
    Tool,
    ToolAnnotations,
    ToolExecutor,
)


class MockAction(ActionBase):
    """Mock action class for testing."""

    command: str = Field(description="Command to execute")
    optional_field: Optional[str] = Field(default=None, description="Optional field")
    nested: Dict[str, Any] = Field(default_factory=dict, description="Nested object")
    array_field: List[int] = Field(default_factory=list, description="Array field")


class MockObservation(ObservationBase):
    """Mock observation class for testing."""

    result: str = Field(description="Result of the action")
    extra_field: Optional[str] = Field(default=None, description="Extra field")


class TestTool:
    """Test cases for the Tool class."""

    def test_tool_creation_basic(self):
        """Test basic tool creation."""
        tool = Tool(
            name="test_tool",
            description="A test tool",
            input_schema=MockAction,
            output_schema=MockObservation,
        )

        assert tool.name == "test_tool"
        assert tool.description == "A test tool"
        assert tool.action_type == MockAction
        assert tool.observation_type == MockObservation
        assert tool.executor is None

    def test_tool_creation_with_executor(self):
        """Test tool creation with executor function."""

        class MockExecutor(ToolExecutor):
            def __call__(self, action: MockAction) -> MockObservation:
                return MockObservation(result=f"Executed: {action.command}")

        tool = Tool(
            name="test_tool",
            description="A test tool",
            input_schema=MockAction,
            output_schema=MockObservation,
            executor=MockExecutor(),
        )

        assert tool.executor is not None
        action = MockAction(command="test")
        result = tool.call(action)
        assert isinstance(result, MockObservation)
        assert result.result == "Executed: test"

    def test_tool_creation_with_annotations(self):
        """Test tool creation with annotations."""
        annotations = ToolAnnotations(
            title="Annotated Tool",
            readOnlyHint=True,
            destructiveHint=False,
        )

        tool = Tool(
            name="test_tool",
            description="A test tool",
            input_schema=MockAction,
            output_schema=MockObservation,
            annotations=annotations,
        )

        assert tool.annotations is not None
        assert tool.annotations == annotations
        assert tool.annotations.title == "Annotated Tool"
        assert tool.annotations.readOnlyHint is True
        assert tool.annotations.destructiveHint is False

    def test_to_mcp_tool_basic(self):
        """Test conversion to MCP tool format."""
        tool = Tool(
            name="test_tool",
            description="A test tool",
            input_schema=MockAction,
            output_schema=MockObservation,
        )

        mcp_tool = tool.to_mcp_tool()

        assert mcp_tool["name"] == "test_tool"
        assert mcp_tool["description"] == "A test tool"
        assert "inputSchema" in mcp_tool
        assert mcp_tool["inputSchema"]["type"] == "object"
        assert "properties" in mcp_tool["inputSchema"]

        # Check that action fields are in the schema
        properties = mcp_tool["inputSchema"]["properties"]
        assert "command" in properties
        assert "optional_field" in properties
        assert "nested" in properties
        assert "array_field" in properties

    def test_to_mcp_tool_with_annotations(self):
        """Test MCP tool conversion with annotations."""
        annotations = ToolAnnotations(
            title="Custom Tool",
            readOnlyHint=True,
        )

        tool = Tool(
            name="test_tool",
            description="A test tool",
            input_schema=MockAction,
            output_schema=MockObservation,
            annotations=annotations,
        )

        mcp_tool = tool.to_mcp_tool()

        # Tool should include annotations
        assert mcp_tool["name"] == "test_tool"
        assert mcp_tool["description"] == "A test tool"
        assert "annotations" in mcp_tool
        assert mcp_tool["annotations"] == annotations

    def test_call_without_executor(self):
        """Test calling tool without executor raises error."""
        tool = Tool(
            name="test_tool",
            description="A test tool",
            input_schema=MockAction,
            output_schema=MockObservation,
        )

        action = MockAction(command="test")
        with pytest.raises(
            NotImplementedError, match="Tool 'test_tool' has no executor"
        ):
            tool.call(action)

    def test_call_with_executor(self):
        """Test calling tool with executor."""

        class MockExecutor(ToolExecutor):
            def __call__(self, action: MockAction) -> MockObservation:
                return MockObservation(result=f"Processed: {action.command}")

        tool = Tool(
            name="test_tool",
            description="A test tool",
            input_schema=MockAction,
            output_schema=MockObservation,
            executor=MockExecutor(),
        )

        action = MockAction(command="test_command")
        result = tool.call(action)

        assert isinstance(result, MockObservation)
        assert result.result == "Processed: test_command"

    def test_schema_generation_complex_types(self):
        """Test schema generation with complex field types."""

        class ComplexAction(ActionBase):
            simple_field: str = Field(description="Simple string field")
            optional_int: int | None = Field(
                default=None, description="Optional integer"
            )
            string_list: list[str] = Field(
                default_factory=list, description="List of strings"
            )

        tool = Tool(
            name="complex_tool",
            description="Tool with complex types",
            input_schema=ComplexAction,
            output_schema=MockObservation,
        )

        mcp_tool = tool.to_mcp_tool()
        properties = mcp_tool["inputSchema"]["properties"]
        assert "simple_field" in properties
        assert properties["simple_field"]["type"] == "string"
        assert "optional_int" in properties
        assert properties["optional_int"]["type"] == "integer"
        assert "string_list" in properties
        assert properties["string_list"]["type"] == "array"
        assert properties["string_list"]["items"]["type"] == "string"

    def test_observation_type_validation(self):
        """Test that observation type is properly validated."""

        class MockExecutor(ToolExecutor):
            def __call__(self, action: MockAction) -> MockObservation:
                return MockObservation(result="success")

        tool = Tool(
            name="test_tool",
            description="A test tool",
            input_schema=MockAction,
            output_schema=MockObservation,
            executor=MockExecutor(),
        )

        action = MockAction(command="test")
        result = tool.call(action)

        # Should return the correct observation type
        assert isinstance(result, MockObservation)
        assert result.result == "success"

    def test_observation_with_extra_fields(self):
        """Test observation with additional fields."""

        class MockExecutor(ToolExecutor):
            def __call__(self, action: MockAction) -> MockObservation:
                return MockObservation(result="test", extra_field="extra_data")

        tool = Tool(
            name="test_tool",
            description="A test tool",
            input_schema=MockAction,
            output_schema=MockObservation,
            executor=MockExecutor(),
        )

        action = MockAction(command="test")
        result = tool.call(action)

        assert isinstance(result, MockObservation)
        assert result.result == "test"
        assert result.extra_field == "extra_data"

    def test_action_validation_with_nested_data(self):
        """Test action validation with nested data structures."""
        tool = Tool(
            name="test_tool",
            description="A test tool",
            input_schema=MockAction,
            output_schema=MockObservation,
        )

        # Create action with nested data
        action_data = {
            "command": "test",
            "nested": {"value": "test"},
            "array_field": [1, 2, 3],
        }
        action = tool.action_type.model_validate(action_data)

        assert isinstance(action, MockAction)
        assert action.nested == {"value": "test"}
        assert action.array_field == [1, 2, 3]
        assert hasattr(action, "optional_field")

    def test_schema_roundtrip_conversion(self):
        """Test that schema conversion is consistent."""
        # Start with a class
        original_schema = MockAction.to_mcp_schema()

        # Create tool and get its schema
        tool = Tool(
            name="test_tool",
            description="A test tool",
            input_schema=MockAction,
            output_schema=MockObservation,
        )
        tool_schema = tool.to_mcp_tool()["inputSchema"]

        # Schemas should be equivalent (ignoring order)
        assert original_schema["type"] == tool_schema["type"]
        assert set(original_schema["properties"].keys()) == set(
            tool_schema["properties"].keys()
        )

    def test_tool_with_no_observation_type(self):
        """Test tool creation with None observation type."""
        tool = Tool(
            name="test_tool",
            description="A test tool",
            input_schema=MockAction,
            output_schema=None,
        )

        assert tool.observation_type is None

        # Should still be able to create MCP tool
        mcp_tool = tool.to_mcp_tool()
        assert mcp_tool["name"] == "test_tool"

    def test_executor_function_attachment(self):
        """Test attaching executor function after tool creation."""
        tool = Tool(
            name="test_tool",
            description="A test tool",
            input_schema=MockAction,
            output_schema=MockObservation,
        )

        # Initially no executor
        assert tool.executor is None

        # Attach executor
        class MockExecutor(ToolExecutor):
            def __call__(self, action: MockAction) -> MockObservation:
                return MockObservation(result=f"Attached: {action.command}")

        tool.executor = MockExecutor()

        # Now it should work
        action = MockAction(command="test")
        result = tool.call(action)
        assert isinstance(result, MockObservation)
        assert result.result == "Attached: test"

    def test_tool_name_validation(self):
        """Test tool name validation."""
        # Valid names should work
        tool = Tool(
            name="valid_tool_name",
            description="A test tool",
            input_schema=MockAction,
            output_schema=MockObservation,
        )
        assert tool.name == "valid_tool_name"

        # Empty name should still work (validation might be elsewhere)
        tool2 = Tool(
            name="",
            description="A test tool",
            input_schema=MockAction,
            output_schema=MockObservation,
        )
        assert tool2.name == ""

    def test_complex_executor_return_types(self):
        """Test executor with complex return types."""

        class ComplexObservation(ObservationBase):
            data: Dict[str, Any] = Field(
                default_factory=dict, description="Complex data"
            )
            count: int = Field(default=0, description="Count field")

        class MockComplexExecutor(ToolExecutor):
            def __call__(self, action: MockAction) -> ComplexObservation:
                return ComplexObservation(
                    data={"processed": action.command, "timestamp": 12345},
                    count=len(action.command) if hasattr(action, "command") else 0,
                )

        tool = Tool(
            name="complex_tool",
            description="Tool with complex observation",
            input_schema=MockAction,
            output_schema=ComplexObservation,
            executor=MockComplexExecutor(),
        )

        action = MockAction(command="test_command")
        result = tool.call(action)

        assert isinstance(result, ComplexObservation)
        assert result.data["processed"] == "test_command"
        assert result.count == len("test_command")

    def test_error_handling_in_executor(self):
        """Test error handling when executor raises exceptions."""

        class FailingExecutor(ToolExecutor):
            def __call__(self, action: MockAction) -> MockObservation:
                raise RuntimeError("Executor failed")

        tool = Tool(
            name="failing_tool",
            description="Tool that fails",
            input_schema=MockAction,
            output_schema=MockObservation,
            executor=FailingExecutor(),
        )

        action = MockAction(command="test")
        with pytest.raises(RuntimeError, match="Executor failed"):
            tool.call(action)

    def test_executor_with_observation_validation(self):
        """Test that executor return values are validated."""

        class StrictObservation(ObservationBase):
            message: str = Field(description="Required message field")
            value: int = Field(description="Required value field")

        class ValidExecutor(ToolExecutor):
            def __call__(self, action: MockAction) -> StrictObservation:
                return StrictObservation(message="success", value=42)

        tool = Tool(
            name="strict_tool",
            description="Tool with strict observation",
            input_schema=MockAction,
            output_schema=StrictObservation,
            executor=ValidExecutor(),
        )

        action = MockAction(command="test")
        result = tool.call(action)
        assert isinstance(result, StrictObservation)
        assert result.message == "success"
        assert result.value == 42

    def test_tool_equality_and_hashing(self):
        """Test tool equality and hashing behavior."""
        tool1 = Tool(
            name="test_tool",
            description="A test tool",
            input_schema=MockAction,
            output_schema=MockObservation,
        )

        tool2 = Tool(
            name="test_tool",
            description="A test tool",
            input_schema=MockAction,
            output_schema=MockObservation,
        )

        # Tools with same parameters should be equal
        assert tool1.name == tool2.name
        assert tool1.description == tool2.description
        assert tool1.action_type == tool2.action_type

    def test_mcp_tool_schema_required_fields(self):
        """Test that MCP tool schema includes required fields."""

        class RequiredFieldAction(ActionBase):
            required_field: str = Field(description="This field is required")
            optional_field: Optional[str] = Field(
                default=None, description="This field is optional"
            )

        tool = Tool(
            name="required_tool",
            description="Tool with required fields",
            input_schema=RequiredFieldAction,
            output_schema=MockObservation,
        )

        mcp_tool = tool.to_mcp_tool()
        schema = mcp_tool["inputSchema"]

        # Check that required fields are marked as required
        assert "required" in schema
        assert "required_field" in schema["required"]
        assert "optional_field" not in schema["required"]

    def test_tool_with_dict_schemas(self):
        """Test tool creation with dictionary schemas."""
        input_schema = {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Input text"},
                "count": {"type": "integer", "description": "Count value"},
            },
            "required": ["text"],
        }

        output_schema = {
            "type": "object",
            "properties": {
                "result": {"type": "string", "description": "Result text"},
            },
            "required": ["result"],
        }

        tool = Tool(
            name="dict_tool",
            description="Tool with dict schemas",
            input_schema=input_schema,
            output_schema=output_schema,
        )

        assert tool.name == "dict_tool"
        assert tool.input_schema == input_schema
        assert tool.output_schema == output_schema

        # Should create dynamic action and observation types
        assert tool.action_type.__name__ == "DictToolAction"
        assert tool.observation_type is not None
        assert tool.observation_type.__name__ == "DictToolObservation"

    def test_tool_with_meta_data(self):
        """Test tool creation with metadata."""
        meta_data = {"version": "1.0", "author": "test"}

        tool = Tool(
            name="meta_tool",
            description="Tool with metadata",
            input_schema=MockAction,
            output_schema=MockObservation,
            _meta=meta_data,
        )

        assert tool._meta == meta_data

        mcp_tool = tool.to_mcp_tool()
        assert "_meta" in mcp_tool
        assert mcp_tool["_meta"] == meta_data

    def test_to_mcp_tool_detailed_type_validation_editor(self):
        """Test detailed type validation for MCP tool schema generation."""
        from openhands.tools.str_replace_editor import (
            str_replace_editor_tool,
        )

        # Test str_replace_editor tool schema
        str_editor_mcp = str_replace_editor_tool.to_mcp_tool()
        str_editor_schema = str_editor_mcp["inputSchema"]
        str_editor_props = str_editor_schema["properties"]

        assert "command" in str_editor_props
        assert "path" in str_editor_props
        assert "file_text" in str_editor_props
        assert "old_str" in str_editor_props
        assert "new_str" in str_editor_props
        assert "insert_line" in str_editor_props
        assert "view_range" in str_editor_props
        assert "security_risk" in str_editor_props

        view_range_schema = str_editor_props["view_range"]
        assert "anyOf" not in view_range_schema
        assert view_range_schema["type"] == "array"
        assert view_range_schema["items"]["type"] == "integer"

        assert "description" in view_range_schema
        assert (
            "Optional parameter of `view` command" in view_range_schema["description"]
        )

        command_schema = str_editor_props["command"]
        assert "enum" in command_schema
        expected_commands = ["view", "create", "str_replace", "insert", "undo_edit"]
        assert set(command_schema["enum"]) == set(expected_commands)

        path_schema = str_editor_props["path"]
        assert path_schema["type"] == "string"
        assert "path" in str_editor_schema["required"]

    def test_to_mcp_tool_detailed_type_validation_bash(self):
        """Test detailed type validation for MCP tool schema generation (execute_bash)."""  # noqa: E501
        from openhands.tools.execute_bash import execute_bash_tool

        # Test execute_bash tool schema
        bash_mcp = execute_bash_tool.to_mcp_tool()
        bash_schema = bash_mcp["inputSchema"]
        bash_props = bash_schema["properties"]

        # Test command field is required string
        bash_command_schema = bash_props["command"]
        assert bash_command_schema["type"] == "string"
        assert "command" in bash_schema["required"]

        # Test is_input field is optional boolean with default
        is_input_schema = bash_props["is_input"]
        assert is_input_schema["type"] == "boolean"
        assert "is_input" not in bash_schema["required"]

        # Test timeout field is optional number
        timeout_schema = bash_props["timeout"]
        assert "anyOf" not in timeout_schema
        assert timeout_schema["type"] == "number"

        # Test security_risk field has enum constraint
        security_risk_schema = bash_props["security_risk"]
        assert "enum" in security_risk_schema
        assert set(security_risk_schema["enum"]) == {"LOW", "MEDIUM", "HIGH"}
        assert "security_risk" in bash_schema["required"]

    def test_to_mcp_tool_complex_nested_types(self):
        """Test MCP tool schema generation with complex nested types."""

        class ComplexNestedAction(ActionBase):
            """Action with complex nested types for testing."""

            simple_string: str = Field(description="Simple string field")
            optional_int: Optional[int] = Field(
                default=None, description="Optional integer"
            )
            string_array: List[str] = Field(
                default_factory=list, description="Array of strings"
            )
            int_array: List[int] = Field(
                default_factory=list, description="Array of integers"
            )
            nested_dict: Dict[str, Any] = Field(
                default_factory=dict, description="Nested dictionary"
            )
            optional_array: Optional[List[str]] = Field(
                default=None, description="Optional array"
            )

        tool = Tool(
            name="complex_nested_tool",
            description="Tool with complex nested types",
            input_schema=ComplexNestedAction,
            output_schema=MockObservation,
        )

        mcp_tool = tool.to_mcp_tool()
        schema = mcp_tool["inputSchema"]
        props = schema["properties"]

        # Test simple string
        assert props["simple_string"]["type"] == "string"
        assert "simple_string" in schema["required"]

        # Test optional int
        optional_int_schema = props["optional_int"]
        assert "anyOf" not in optional_int_schema
        assert optional_int_schema["type"] == "integer"
        assert "optional_int" not in schema["required"]

        # Test string array
        string_array_schema = props["string_array"]
        assert string_array_schema["type"] == "array"
        assert string_array_schema["items"]["type"] == "string"

        # Test int array
        int_array_schema = props["int_array"]
        assert int_array_schema["type"] == "array"
        assert int_array_schema["items"]["type"] == "integer"

        # Test nested dict
        nested_dict_schema = props["nested_dict"]
        assert nested_dict_schema["type"] == "object"

        # Test optional array
        optional_array_schema = props["optional_array"]
        assert "anyOf" not in optional_array_schema
        assert optional_array_schema["type"] == "array"
        assert optional_array_schema["items"]["type"] == "string"
