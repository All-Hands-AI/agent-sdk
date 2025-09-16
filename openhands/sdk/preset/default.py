"""Default preset configuration for OpenHands agents."""

from openhands.sdk import AgentSpec, CondenserSpec, Tool, ToolSpec, create_mcp_tools
from openhands.sdk.context.condenser import (
    Condenser,
    LLMSummarizingCondenser,
)
from openhands.sdk.llm.llm import LLM


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
    # events with an LLM-generated summary.
    condenser = LLMSummarizingCondenser(llm=llm, max_size=80, keep_first=4)

    return condenser


def get_default_agent_spec(
    llm: LLM,
    working_dir: str,
    cli_mode: bool = False,
) -> AgentSpec:
    agent_spec = AgentSpec(
        llm=llm,
        tools=[
            ToolSpec(name="BashTool", params={"working_dir": working_dir}),
            ToolSpec(name="FileEditorTool", params={}),
            ToolSpec(
                name="TaskTrackerTool", params={"save_dir": f"{working_dir}/.openhands"}
            ),
            # A set of browsing tools
            ToolSpec(name="BrowserToolSet", params={}),
        ],
        mcp_config={
            "mcpServers": {
                "fetch": {"command": "uvx", "args": ["mcp-server-fetch"]},
                "repomix": {"command": "npx", "args": ["-y", "repomix@1.4.2", "--mcp"]},
            }
        },
        filter_tools_regex="^(?!repomix)(.*)|^repomix.*pack_codebase.*$",
        system_prompt_kwargs={"cli_mode": cli_mode},
        condenser=CondenserSpec(
            name="LLMSummarizingCondenser",
            params={"llm": llm, "max_size": 80, "keep_first": 4},
        ),
    )
    return agent_spec
