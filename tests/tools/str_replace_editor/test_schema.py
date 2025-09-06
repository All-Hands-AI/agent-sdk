from openhands.tools.str_replace_editor import str_replace_editor_tool


def test_to_mcp_tool_detailed_type_validation_editor():
    """Test detailed type validation for MCP tool schema generation."""

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
    assert "Optional parameter of `view` command" in view_range_schema["description"]

    command_schema = str_editor_props["command"]
    assert "enum" in command_schema
    expected_commands = ["view", "create", "str_replace", "insert", "undo_edit"]
    assert set(command_schema["enum"]) == set(expected_commands)

    path_schema = str_editor_props["path"]
    assert path_schema["type"] == "string"
    assert "path" in str_editor_schema["required"]
