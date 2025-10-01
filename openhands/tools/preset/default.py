"""Default preset configuration for OpenHands agents."""

from openhands.sdk import Agent
from openhands.sdk.context.condenser import (
    LLMSummarizingCondenser,
)
from openhands.sdk.context.condenser.base import CondenserBase
from openhands.sdk.llm.llm import LLM
from openhands.sdk.logger import get_logger
from openhands.sdk.security.llm_analyzer import LLMSecurityAnalyzer
from openhands.sdk.tool import ToolSpec, register_tool


logger = get_logger(__name__)


def register_default_tools(enable_browser: bool = True) -> None:
    """Register the default set of tools.

    If a tool name is already registered, we do not override it. This allows
    callers (e.g., tests) to inject lightweight factories without being
    clobbered by the default preset registration.
    """
    from openhands.sdk.tool import list_registered_tools
    from openhands.tools.execute_bash import BashTool
    from openhands.tools.str_replace_editor import FileEditorTool
    from openhands.tools.task_tracker import TaskTrackerTool

    already = set(list_registered_tools())

    if "BashTool" not in already:
        register_tool("BashTool", BashTool)
        logger.debug("Tool: BashTool registered.")
    else:
        logger.debug("Tool: BashTool already registered - skipping preset override.")

    if "FileEditorTool" not in already:
        register_tool("FileEditorTool", FileEditorTool)
        logger.debug("Tool: FileEditorTool registered.")
    else:
        logger.debug(
            "Tool: FileEditorTool already registered - skipping preset override."
        )

    if "TaskTrackerTool" not in already:
        register_tool("TaskTrackerTool", TaskTrackerTool)
        logger.debug("Tool: TaskTrackerTool registered.")
    else:
        logger.debug(
            "Tool: TaskTrackerTool already registered - skipping preset override."
        )

    if enable_browser:
        from openhands.tools.browser_use import BrowserToolSet

        if "BrowserToolSet" not in already:
            register_tool("BrowserToolSet", BrowserToolSet)
            logger.debug("Tool: BrowserToolSet registered.")
        else:
            logger.debug(
                "Tool: BrowserToolSet already registered - skipping preset override."
            )


def get_default_tools(
    enable_browser: bool = True,
) -> list[ToolSpec]:
    """Get the default set of tool specifications for the standard experience.

    Args:
        enable_browser: Whether to include browser tools.
    """
    register_default_tools(enable_browser=enable_browser)

    tool_specs = [
        ToolSpec(name="BashTool"),
        ToolSpec(name="FileEditorTool"),
        ToolSpec(name="TaskTrackerTool"),
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
    cli_mode: bool = False,
) -> Agent:
    tool_specs = get_default_tools(
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
        condenser=get_default_condenser(
            llm=llm.model_copy(update={"service_id": "condenser"})
        ),
        security_analyzer=LLMSecurityAnalyzer(),
    )
    return agent
