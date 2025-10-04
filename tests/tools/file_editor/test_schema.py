import tempfile
from uuid import uuid4

from pydantic import SecretStr

from openhands.sdk.agent import Agent
from openhands.sdk.conversation.state import ConversationState
from openhands.sdk.llm import LLM
from openhands.sdk.workspace import LocalWorkspace
from openhands.tools.file_editor import FileEditorTool


def test_to_mcp_tool_detailed_type_validation_editor():
    """Test detailed type validation for MCP tool schema generation."""

    # Create a test conversation state
    with tempfile.TemporaryDirectory() as temp_dir:
        llm = LLM(
            model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="test-llm"
        )
        agent = Agent(llm=llm, tools=[])
        conv_state = ConversationState.create(
            id=uuid4(),
            agent=agent,
            workspace=LocalWorkspace(working_dir=temp_dir),
        )

        # Test file_editor tool schema
        file_editor_tools = FileEditorTool.create(conv_state)
        str_editor_mcp = file_editor_tools[0].to_mcp_tool()
        str_editor_schema = str_editor_mcp["inputSchema"]
        str_editor_props = str_editor_schema["properties"]

        assert "command" in str_editor_props
        assert "path" in str_editor_props
        assert "file_text" in str_editor_props
        assert "old_str" in str_editor_props
        assert "new_str" in str_editor_props
        assert "insert_line" in str_editor_props
        assert "view_range" in str_editor_props
        # security_risk should NOT be in the schema after #341
        assert "security_risk" not in str_editor_props

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
