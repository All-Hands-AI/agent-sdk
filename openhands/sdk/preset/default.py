"""Default preset configuration for OpenHands agents."""

from openhands.sdk import LLM, Tool, create_mcp_tools
from openhands.sdk.context.condenser import (
    Condenser,
    LLMSummarizingCondenser,
)


def get_default_tools(working_dir: str) -> list[Tool]:
    """Get the default set of tools including MCP tools if configured."""
    from openhands.tools import BashTool, FileEditorTool, TaskTrackerTool

    tools = [
        BashTool.create(working_dir=working_dir),
        FileEditorTool.create(),
        TaskTrackerTool.create(),
    ]

    # Add MCP Tools
    mcp_config = {
        "mcpServers": {
            "fetch": {"command": "uvx", "args": ["mcp-server-fetch"]},
            "repomix": {"command": "npx", "args": ["-y", "repomix@1.4.2", "--mcp"]},
        }
    }
    _mcp_tools = create_mcp_tools(config=mcp_config)
    for tool in _mcp_tools:
        # Only select part of the "repomix" tools
        if "repomix" in tool.name:
            if "pack_codebase" in tool.name:
                tools.append(tool)
        else:
            tools.append(tool)
    return tools


def get_default_condenser(llm: LLM) -> Condenser:
    # Create a condenser to manage the context. The condenser will automatically
    # truncate conversation history when it exceeds max_size, and replaces the dropped
    # events with an LLM-generated summary. This condenser triggers when there are more
    # than ten events in the conversation history, and always keeps the first two events
    # (system prompts, initial user messages) to preserve important context.
    condenser = LLMSummarizingCondenser(llm=llm, max_size=10, keep_first=2)

    return condenser
