import tempfile
from openhands.tools.execute_bash import BashTool


def test_to_mcp_tool_detailed_type_validation_bash():
    """Test detailed type validation for MCP tool schema generation (execute_bash)."""  # noqa: E501

    # Test execute_bash tool schema
    with tempfile.TemporaryDirectory() as temp_dir:
        bash_tool = BashTool.create(working_dir=temp_dir)
        bash_mcp = bash_tool.to_mcp_tool()
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
    assert "security_risk" in bash_props
    security_risk_schema = bash_props["security_risk"]
    assert "enum" in security_risk_schema
    assert set(security_risk_schema["enum"]) == {"LOW", "MEDIUM", "HIGH", "UNKNOWN"}
