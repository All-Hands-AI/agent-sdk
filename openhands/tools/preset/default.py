"""Default preset configuration for OpenHands agents."""

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


def register_default_tools(
    enable_browser: bool = True, enable_delegation: bool = True
) -> None:
    """Register the default set of tools."""
    from openhands.tools.execute_bash import BashTool
    from openhands.tools.file_editor import FileEditorTool
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

    if enable_delegation:
        from openhands.tools.delegation import DelegationTool

        register_tool("DelegationTool", DelegationTool)
        logger.debug("Tool: DelegationTool registered.")


def get_default_tools(
    enable_browser: bool = True,
    enable_delegation: bool = True,
) -> list[Tool]:
    """Get the default set of tool specifications for the standard experience.

    Args:
        enable_browser: Whether to include browser tools.
        enable_delegation: Whether to include delegation tools.
    """
    register_default_tools(
        enable_browser=enable_browser, enable_delegation=enable_delegation
    )

    tools = [
        Tool(name="BashTool"),
        Tool(name="FileEditorTool"),
        Tool(name="TaskTrackerTool"),
    ]
    if enable_browser:
        tools.append(Tool(name="BrowserToolSet"))
    if enable_delegation:
        tools.append(Tool(name="DelegationTool"))
    return tools


def get_default_condenser(llm: LLM) -> CondenserBase:
    # Create a condenser to manage the context. The condenser will automatically
    # truncate conversation history when it exceeds max_size, and replaces the dropped
    # events with an LLM-generated summary.
    condenser = LLMSummarizingCondenser(llm=llm, max_size=80, keep_first=4)

    return condenser


def get_default_agent(
    llm: LLM,
    cli_mode: bool = False,
    enable_delegation: bool = True,
) -> Agent:
    """Get the default agent with delegation capabilities.

    This agent includes delegation tools and can spawn worker agents.

    Args:
        llm: The LLM to use for the agent
        cli_mode: Whether to run in CLI mode (disables browser tools)
        enable_delegation: Whether to include delegation tools
    """
    tools = get_default_tools(
        # Disable browser tools in CLI mode
        enable_browser=not cli_mode,
        enable_delegation=enable_delegation,
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
        condenser=get_default_condenser(
            llm=llm.model_copy(update={"service_id": "condenser"})
        ),
        security_analyzer=LLMSecurityAnalyzer(),
    )
    return agent
