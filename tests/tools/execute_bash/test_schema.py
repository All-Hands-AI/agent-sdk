from openhands_tools.execute_bash import execute_bash_tool


def test_to_mcp_tool_detailed_type_validation_bash():
    """Test detailed type validation for MCP tool schema generation (execute_bash)."""  # noqa: E501

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

    # security_risk should NOT be in the schema after #341
    assert "security_risk" not in bash_props
