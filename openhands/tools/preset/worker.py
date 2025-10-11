"""Worker agent preset configuration for OpenHands agents.

This preset creates worker agents that can be used as sub-agents
in delegation scenarios. Worker agents have the same capabilities
as default agents but without delegation tools to prevent infinite
recursion.
"""

from openhands.sdk import Agent
from openhands.sdk.context.condenser import (
    LLMSummarizingCondenser,
)
from openhands.sdk.context.condenser.base import CondenserBase
from openhands.sdk.llm.llm import LLM
from openhands.sdk.logger import get_logger
from openhands.sdk.security.llm_analyzer import LLMSecurityAnalyzer
from openhands.sdk.tool import Tool, register_tool


logger = get_logger(__name__)


def register_worker_tools(enable_browser: bool = True) -> None:
    """Register the worker agent tools (same as default but without delegation)."""
    from openhands.tools.execute_bash import BashTool
    from openhands.tools.file_editor import FileEditorTool
    from openhands.tools.task_tracker import TaskTrackerTool

    register_tool("BashTool", BashTool)
    logger.debug("Tool: BashTool registered for worker.")
    register_tool("FileEditorTool", FileEditorTool)
    logger.debug("Tool: FileEditorTool registered for worker.")
    register_tool("TaskTrackerTool", TaskTrackerTool)
    logger.debug("Tool: TaskTrackerTool registered for worker.")

    if enable_browser:
        from openhands.tools.browser_use import BrowserToolSet

        register_tool("BrowserToolSet", BrowserToolSet)
        logger.debug("Tool: BrowserToolSet registered for worker.")


def get_worker_tools(
    enable_browser: bool = True,
) -> list[Tool]:
    """Get the worker agent tools (same as default but without delegation).

    Args:
        enable_browser: Whether to include browser tools.
    """
    register_worker_tools(enable_browser=enable_browser)

    tools = [
        Tool(name="BashTool"),
        Tool(name="FileEditorTool"),
        Tool(name="TaskTrackerTool"),
    ]
    if enable_browser:
        tools.append(Tool(name="BrowserToolSet"))
    return tools


def get_worker_condenser(llm: LLM) -> CondenserBase:
    """Get the condenser for worker agents."""
    # Create a condenser to manage the context. The condenser will automatically
    # truncate conversation history when it exceeds max_size, and replaces the dropped
    # events with an LLM-generated summary.
    condenser = LLMSummarizingCondenser(llm=llm, max_size=80, keep_first=4)

    return condenser


def get_worker_agent(
    llm: LLM,
    cli_mode: bool = False,
) -> Agent:
    """Get a worker agent that can be used as a sub-agent for delegation.

    This agent is identical to the default agent but without delegation tools.
    It's designed to be used as a sub-agent by the main agent with delegation.

    Args:
        llm: The LLM to use for the agent
        cli_mode: Whether to run in CLI mode (disables browser tools)
    """
    tools = get_worker_tools(
        # Disable browser tools in CLI mode
        enable_browser=not cli_mode,
    )
    agent = Agent(
        llm=llm,
        tools=tools,
        mcp_config={
            "mcpServers": {
                "fetch": {"command": "uvx", "args": ["mcp-server-fetch"]},
                "repomix": {"command": "npx", "args": ["-y", "repomix@1.4.2", "--mcp"]},
            }
        },
        filter_tools_regex="^(?!repomix)(.*)|^repomix.*pack_codebase.*$",
        system_prompt_kwargs={"cli_mode": cli_mode},
        condenser=get_worker_condenser(
            llm=llm.model_copy(update={"service_id": "worker_condenser"})
        ),
        security_analyzer=LLMSecurityAnalyzer(),
    )
    return agent
