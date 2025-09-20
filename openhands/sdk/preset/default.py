"""Default preset configuration for OpenHands agents."""

from openhands.sdk import Agent
from openhands.sdk.context.condenser import (
    LLMSummarizingCondenser,
)
from openhands.sdk.context.condenser.base import CondenserBase
from openhands.sdk.llm.llm import LLM
from openhands.sdk.tool import ToolSpec, register_tool


def get_default_tools(working_dir: str) -> list[ToolSpec]:
    """Get the default set of tool specifications for the standard experience."""
    from openhands.tools.browser_use import BrowserToolSet
    from openhands.tools.execute_bash import BashTool
    from openhands.tools.str_replace_editor import FileEditorTool
    from openhands.tools.task_tracker import TaskTrackerTool

    register_tool("BashTool", BashTool)
    register_tool("FileEditorTool", FileEditorTool)
    register_tool("TaskTrackerTool", TaskTrackerTool)
    register_tool("BrowserToolSet", BrowserToolSet)

    return [
        ToolSpec(name="BashTool", params={"working_dir": working_dir}),
        ToolSpec(name="FileEditorTool", params={}),
        ToolSpec(
            name="TaskTrackerTool", params={"save_dir": f"{working_dir}/.openhands"}
        ),
        ToolSpec(name="BrowserToolSet", params={}),
    ]


def get_default_condenser(llm: LLM) -> CondenserBase:
    # Create a condenser to manage the context. The condenser will automatically
    # truncate conversation history when it exceeds max_size, and replaces the dropped
    # events with an LLM-generated summary.
    condenser = LLMSummarizingCondenser(llm=llm, max_size=80, keep_first=4)

    return condenser


def get_default_agent_spec(
    llm: LLM,
    working_dir: str,
    cli_mode: bool = False,
) -> Agent:
    tool_specs = get_default_tools(working_dir=working_dir)
    agent = Agent(
        llm=llm,
        tools=tool_specs,
        mcp_config={
            "mcpServers": {
                "fetch": {"command": "uvx", "args": ["mcp-server-fetch"]},
                "repomix": {"command": "npx", "args": ["-y", "repomix@1.4.2", "--mcp"]},
            }
        },
        filter_tools_regex="^(?!repomix)(.*)|^repomix.*pack_codebase.*$",
        system_prompt_kwargs={"cli_mode": cli_mode},
        condenser=LLMSummarizingCondenser(llm=llm, max_size=80, keep_first=4),
    )
    return agent
