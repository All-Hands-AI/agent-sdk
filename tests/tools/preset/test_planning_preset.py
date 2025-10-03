"""Tests for planning agent preset configuration."""

from unittest.mock import Mock, patch

from openhands.sdk.llm import LLM
from openhands.tools.preset.planning import (
    get_planning_agent,
    get_planning_condenser,
    get_planning_tools,
    register_planning_tools,
)


def test_register_planning_tools():
    """Test that planning tools are registered correctly."""
    # This should not raise any exceptions
    register_planning_tools()


def test_get_planning_tools():
    """Test that planning tools are returned correctly."""
    tools = get_planning_tools()

    assert len(tools) == 4
    tool_names = [tool.name for tool in tools]
    assert "BashTool" in tool_names
    assert "FileEditorTool" in tool_names
    assert "PlanWriterTool" in tool_names
    assert "TaskTrackerTool" in tool_names

    # Check that FileEditorTool has read_only parameter set to True
    file_editor_tool = next(tool for tool in tools if tool.name == "FileEditorTool")
    assert file_editor_tool.params == {"read_only": True}


@patch("openhands.tools.preset.planning.LLMSummarizingCondenser")
def test_get_planning_condenser(mock_condenser_class):
    """Test that planning condenser is configured correctly."""
    mock_llm = Mock(spec=LLM)
    mock_condenser = Mock()
    mock_condenser_class.return_value = mock_condenser

    condenser = get_planning_condenser(mock_llm)

    # Check that condenser was created with correct parameters
    mock_condenser_class.assert_called_once_with(
        llm=mock_llm, max_size=100, keep_first=6
    )
    assert condenser == mock_condenser


@patch("openhands.tools.preset.planning.get_planning_condenser")
@patch("openhands.tools.preset.planning.PlanningAgent")
def test_get_planning_agent(mock_agent_class, mock_get_condenser):
    """Test that planning agent is created with correct configuration."""
    mock_llm = Mock(spec=LLM)
    mock_condenser = Mock()
    mock_get_condenser.return_value = mock_condenser
    mock_agent = Mock()
    mock_agent_class.return_value = mock_agent

    agent = get_planning_agent(mock_llm)

    # Verify condenser was created with model_copy
    mock_get_condenser.assert_called_once()
    call_args = mock_get_condenser.call_args[1]
    assert "llm" in call_args

    # Verify agent was created with correct parameters
    mock_agent_class.assert_called_once()
    call_kwargs = mock_agent_class.call_args[1]
    assert call_kwargs["llm"] == mock_llm
    assert call_kwargs["condenser"] == mock_condenser
    assert len(call_kwargs["tools"]) > 0
    assert call_kwargs["security_analyzer"] is not None

    assert agent == mock_agent


@patch("openhands.tools.preset.planning.get_planning_condenser")
@patch("openhands.tools.preset.planning.PlanningAgent")
def test_get_planning_agent_no_security(mock_agent_class, mock_get_condenser):
    """Test creating planning agent without security analyzer."""
    mock_llm = Mock(spec=LLM)
    mock_condenser = Mock()
    mock_get_condenser.return_value = mock_condenser
    mock_agent = Mock()
    mock_agent_class.return_value = mock_agent

    agent = get_planning_agent(mock_llm, enable_security_analyzer=False)

    # Verify agent was created with security analyzer disabled
    call_kwargs = mock_agent_class.call_args[1]
    assert call_kwargs["security_analyzer"] is None

    assert agent == mock_agent


def test_file_editor_tool_read_only_functionality():
    """Test that FileEditorTool properly enforces read_only restrictions."""
    from openhands.tools.str_replace_editor.definition import StrReplaceEditorAction
    from openhands.tools.str_replace_editor.impl import FileEditorExecutor

    # Test read_only=True executor
    read_only_executor = FileEditorExecutor(read_only=True)

    # Test that view command works (would not be blocked by read_only check)
    # We can't actually test the file operation without a real file

    # Test that write commands are blocked
    create_action = StrReplaceEditorAction(
        command="create", path="/tmp/test.txt", file_text="test content"
    )
    result = read_only_executor(create_action)
    assert result.error is not None
    assert "not allowed in read-only mode" in result.error
    assert "Only 'view' and 'list' commands are permitted" in result.error

    # Test str_replace is blocked
    replace_action = StrReplaceEditorAction(
        command="str_replace", path="/tmp/test.txt", old_str="old", new_str="new"
    )
    result = read_only_executor(replace_action)
    assert result.error is not None
    assert "not allowed in read-only mode" in result.error

    # Test insert is blocked
    insert_action = StrReplaceEditorAction(
        command="insert", path="/tmp/test.txt", new_str="new content", insert_line=1
    )
    result = read_only_executor(insert_action)
    assert result.error is not None
    assert "not allowed in read-only mode" in result.error

    # Test undo_edit is blocked
    undo_action = StrReplaceEditorAction(command="undo_edit", path="/tmp/test.txt")
    result = read_only_executor(undo_action)
    assert result.error is not None
    assert "not allowed in read-only mode" in result.error
