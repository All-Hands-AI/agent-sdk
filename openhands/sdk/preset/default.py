"""Default preset configuration for OpenHands agents."""

from openhands.sdk import Tool, create_mcp_tools


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
