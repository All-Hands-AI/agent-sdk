"""Test directory handling in tool registry."""

import os
import tempfile

import pytest
from pydantic import SecretStr

from openhands.sdk.agent.base import AgentBase
from openhands.sdk.conversation import Conversation
from openhands.sdk.conversation.base import BaseConversation
from openhands.sdk.conversation.state import ConversationState
from openhands.sdk.conversation.types import ConversationCallbackType
from openhands.sdk.event.llm_convertible import SystemPromptEvent
from openhands.sdk.llm import LLM, TextContent
from openhands.sdk.tool.registry import resolve_tool
from openhands.sdk.tool.spec import ToolSpec
from openhands.tools.execute_bash import BashTool
from openhands.tools.str_replace_editor import FileEditorTool
from openhands.tools.task_tracker import TaskTrackerTool


class DummyAgent(AgentBase):
    """Test agent for directory testing."""

    def __init__(self):
        llm = LLM(
            model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="test-llm"
        )
        super().__init__(llm=llm, tools=[])

    def init_state(
        self, state: ConversationState, on_event: ConversationCallbackType
    ) -> None:
        event = SystemPromptEvent(
            source="agent", system_prompt=TextContent(text="test agent"), tools=[]
        )
        on_event(event)

    def step(self, state: BaseConversation, on_event: ConversationCallbackType) -> None:
        pass


@pytest.fixture
def test_agent():
    """Create a test agent for testing."""
    return DummyAgent()


@pytest.fixture(autouse=True)
def register_tools():
    """Register tools for testing."""
    from openhands.sdk.tool import register_tool

    register_tool("BashTool", BashTool)
    register_tool("FileEditorTool", FileEditorTool)
    register_tool("TaskTrackerTool", TaskTrackerTool)


def test_resolve_tool_with_conversation_directories(test_agent):
    """Test that resolve_tool uses directories from conversation."""
    with tempfile.TemporaryDirectory() as temp_dir:
        working_dir = os.path.join(temp_dir, "work")
        persistence_dir = os.path.join(temp_dir, "persist")
        os.makedirs(working_dir)
        os.makedirs(persistence_dir)

        conversation = Conversation(
            agent=test_agent,
            persistence_dir=persistence_dir,
            working_dir=working_dir,
        )

        # Test BashTool
        bash_spec = ToolSpec(name="BashTool")
        bash_tools = resolve_tool(bash_spec, conversation=conversation._state)
        assert len(bash_tools) == 1
        # Type ignore needed for test-specific executor access
        work_dir = bash_tools[0].executor.session.work_dir  # type: ignore[attr-defined]
        assert work_dir == working_dir

        # Test FileEditorTool
        editor_spec = ToolSpec(name="FileEditorTool")
        editor_tools = resolve_tool(editor_spec, conversation=conversation._state)
        assert len(editor_tools) == 1
        # Type ignore needed for test-specific executor access
        cwd = str(editor_tools[0].executor.editor._cwd)  # type: ignore[attr-defined]
        assert cwd == working_dir

        # Test TaskTrackerTool
        tracker_spec = ToolSpec(name="TaskTrackerTool")
        tracker_tools = resolve_tool(tracker_spec, conversation=conversation._state)
        assert len(tracker_tools) == 1
        # Type ignore needed for test-specific executor access
        save_dir = str(tracker_tools[0].executor.save_dir)  # type: ignore[attr-defined]
        assert save_dir == persistence_dir


def test_resolve_tool_without_conversation():
    """Test that resolve_tool works without conversation (backward compatibility)."""
    with tempfile.TemporaryDirectory() as temp_dir:
        working_dir = os.path.join(temp_dir, "work")
        os.makedirs(working_dir)

        # Test BashTool with explicit working_dir
        bash_spec = ToolSpec(name="BashTool", params={"working_dir": working_dir})
        bash_tools = resolve_tool(bash_spec)
        assert len(bash_tools) == 1
        # Type ignore needed for test-specific executor access
        work_dir = bash_tools[0].executor.session.work_dir  # type: ignore[attr-defined]
        assert work_dir == working_dir

        # Test FileEditorTool with explicit workspace_root
        editor_spec = ToolSpec(
            name="FileEditorTool", params={"workspace_root": working_dir}
        )
        editor_tools = resolve_tool(editor_spec)
        assert len(editor_tools) == 1
        # Type ignore needed for test-specific executor access
        cwd = str(editor_tools[0].executor.editor._cwd)  # type: ignore[attr-defined]
        assert cwd == working_dir

        # Test TaskTrackerTool with explicit save_dir
        tracker_spec = ToolSpec(
            name="TaskTrackerTool", params={"save_dir": working_dir}
        )
        tracker_tools = resolve_tool(tracker_spec)
        assert len(tracker_tools) == 1
        # Type ignore needed for test-specific executor access
        save_dir = str(tracker_tools[0].executor.save_dir)  # type: ignore[attr-defined]
        assert save_dir == working_dir


def test_resolve_tool_explicit_params_override(test_agent):
    """Test that explicit params take precedence over conversation directories."""
    with tempfile.TemporaryDirectory() as temp_dir:
        conversation_work_dir = os.path.join(temp_dir, "conversation_work")
        conversation_persist_dir = os.path.join(temp_dir, "conversation_persist")
        param_work_dir = os.path.join(temp_dir, "param_work")
        param_persist_dir = os.path.join(temp_dir, "param_persist")

        os.makedirs(conversation_work_dir)
        os.makedirs(conversation_persist_dir)
        os.makedirs(param_work_dir)
        os.makedirs(param_persist_dir)

        conversation = Conversation(
            agent=test_agent,
            persistence_dir=conversation_persist_dir,
            working_dir=conversation_work_dir,
        )

        # Test BashTool - explicit params should take precedence
        bash_spec = ToolSpec(name="BashTool", params={"working_dir": param_work_dir})
        bash_tools = resolve_tool(bash_spec, conversation=conversation._state)
        assert len(bash_tools) == 1
        # Type ignore needed for test-specific executor access
        work_dir = bash_tools[0].executor.session.work_dir  # type: ignore[attr-defined]
        assert work_dir == param_work_dir

        # Test TaskTrackerTool - explicit params should take precedence
        tracker_spec = ToolSpec(
            name="TaskTrackerTool", params={"save_dir": param_persist_dir}
        )
        tracker_tools = resolve_tool(tracker_spec, conversation=conversation._state)
        assert len(tracker_tools) == 1
        # Type ignore needed for test-specific executor access
        save_dir = str(tracker_tools[0].executor.save_dir)  # type: ignore[attr-defined]
        assert save_dir == param_persist_dir
