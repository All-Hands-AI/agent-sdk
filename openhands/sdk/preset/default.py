"""Default preset configuration for OpenHands agents."""

import os

from openhands.sdk import Agent
from openhands.sdk.context.condenser import (
    LLMSummarizingCondenser,
)
from openhands.sdk.context.condenser.base import CondenserBase
from openhands.sdk.llm.llm import LLM
from openhands.sdk.logger import get_logger
from openhands.sdk.tool import ToolSpec, register_tool


logger = get_logger(__name__)


def register_default_tools(enable_browser: bool = True) -> None:
    """Register the default set of tools."""
    from openhands.tools.execute_bash import BashTool
    from openhands.tools.str_replace_editor import FileEditorTool
    from openhands.tools.task_tracker import TaskTrackerTool

    register_tool("BashTool", BashTool)
    logger.debug("Tool: BashTool registered.")
    register_tool("FileEditorTool", FileEditorTool)
    logger.debug("Tool: FileEditorTool registered.")
    register_tool("TaskTrackerTool", TaskTrackerTool)
    logger.debug("Tool: TaskTrackerTool registered.")

    if enable_browser:
        from openhands.tools.browser_use import BrowserToolSet

        register_tool("BrowserToolSet", BrowserToolSet)
        logger.debug("Tool: BrowserToolSet registered.")


def get_default_tools(
    working_dir: str,
    persistence_dir: str | None = None,
    enable_browser: bool = True,
) -> list[ToolSpec]:
    """Get the default set of tool specifications for the standard experience."""
    register_default_tools(enable_browser=enable_browser)

    persistence_path = persistence_dir or os.path.join(working_dir, ".openhands")
    tool_specs = [
        ToolSpec(name="BashTool", params={"working_dir": working_dir}),
        ToolSpec(name="FileEditorTool", params={"workspace_root": working_dir}),
        ToolSpec(name="TaskTrackerTool", params={"save_dir": persistence_path}),
    ]
    if enable_browser:
        tool_specs.append(ToolSpec(name="BrowserToolSet"))
    return tool_specs


def get_default_condenser(llm: LLM) -> CondenserBase:
    # Create a condenser to manage the context. The condenser will automatically
    # truncate conversation history when it exceeds max_size, and replaces the dropped
    # events with an LLM-generated summary.
    condenser = LLMSummarizingCondenser(llm=llm, max_size=80, keep_first=4)

    return condenser


def get_default_agent(
    llm: LLM,
    working_dir: str,
    persistence_dir: str | None = None,
    cli_mode: bool = False,
) -> Agent:
    tool_specs = get_default_tools(
        working_dir=working_dir,
        persistence_dir=persistence_dir,
        # Disable browser tools in CLI mode
        enable_browser=not cli_mode,
    )
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
        condenser=get_default_condenser(llm=llm),
    )
    return agent
