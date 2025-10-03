"""Planning agent preset configuration."""

from openhands.sdk import Agent
from openhands.sdk.context.condenser import LLMSummarizingCondenser
from openhands.sdk.llm.llm import LLM
from openhands.sdk.logger import get_logger
from openhands.sdk.tool import Tool, register_tool


logger = get_logger(__name__)


def register_planning_tools() -> None:
    """Register the planning agent tools."""
    from openhands.tools.file_viewer import FileViewerTool
    from openhands.tools.glob import GlobTool
    from openhands.tools.grep import GrepTool
    from openhands.tools.plan_writer import PlanWriterTool
    from openhands.tools.task_tracker import TaskTrackerTool

    register_tool("GlobTool", GlobTool)
    logger.debug("Tool: GlobTool registered.")
    register_tool("GrepTool", GrepTool)
    logger.debug("Tool: GrepTool registered.")
    register_tool("FileViewerTool", FileViewerTool)
    logger.debug("Tool: FileViewerTool registered.")
    register_tool("PlanWriterTool", PlanWriterTool)
    logger.debug("Tool: PlanWriterTool registered.")
    register_tool("TaskTrackerTool", TaskTrackerTool)
    logger.debug("Tool: TaskTrackerTool registered.")


def get_planning_tools() -> list[Tool]:
    """Get the planning agent tool specifications.

    Returns:
        List of tools optimized for planning and analysis tasks, including
        read-only file operations and command-line capabilities for advanced
        code discovery and navigation.
    """
    register_planning_tools()

    return [
        Tool(name="GlobTool"),
        Tool(name="GrepTool"),
        Tool(name="FileViewerTool"),
        Tool(name="PlanWriterTool"),
        Tool(name="TaskTrackerTool"),
    ]


def get_planning_condenser(llm: LLM) -> LLMSummarizingCondenser:
    """Get a condenser optimized for planning workflows.

    Args:
        llm: The LLM to use for condensation.

    Returns:
        A condenser configured for planning agent needs.
    """
    # Planning agents may need more context for thorough analysis
    condenser = LLMSummarizingCondenser(
        llm=llm,
        max_size=100,  # Larger context window for planning
        keep_first=6,  # Keep more initial context
    )
    return condenser


def get_planning_agent(
    llm: LLM,
) -> Agent:
    """Get a configured planning agent.

    Args:
        llm: The LLM to use for the planning agent.
        enable_security_analyzer: Whether to enable security analysis.

    Returns:
        A fully configured planning agent with read-only file operations and
        command-line capabilities for comprehensive code discovery.
    """
    tools = get_planning_tools()

    # Add MCP tools that are useful for planning
    mcp_config = {
        "mcpServers": {
            "fetch": {"command": "uvx", "args": ["mcp-server-fetch"]},
            "repomix": {"command": "npx", "args": ["-y", "repomix@1.4.2", "--mcp"]},
        }
    }

    # Filter to only read-only MCP tools
    filter_tools_regex = "^(?!repomix)(.*)|^repomix.*pack_codebase.*$"

    agent = Agent(
        llm=llm,
        tools=tools,
        mcp_config=mcp_config,
        filter_tools_regex=filter_tools_regex,
        system_prompt_filename="planning_system_prompt.j2",
        condenser=get_planning_condenser(
            llm=llm.model_copy(update={"service_id": "planning_condenser"})
        ),
        security_analyzer=None,
    )

    return agent
