from typing import Any

from pydantic import BaseModel, Field

from openhands.sdk.context.agent_context import AgentContext
from openhands.sdk.context.condenser import CondenserSpec
from openhands.sdk.llm import LLM
from openhands.sdk.tool import ToolSpec


class AgentSpec(BaseModel):
    """Everything needed for creating an agent.

    This is used to create an agent in the server via one API request.
    """

    llm: LLM = Field(
        ...,
        description="LLM configuration for the agent.",
        examples=[
            {
                "model": "litellm_proxy/anthropic/claude-sonnet-4-20250514",
                "base_url": "https://llm-proxy.eval.all-hands.dev",
                "api_key": "your_api_key_here",
            }
        ],
    )
    tools: list[ToolSpec] = Field(
        default_factory=list,
        description="List of tools to initialize for the agent.",
        examples=[
            {"name": "BashTool", "params": {"working_dir": "/workspace"}},
            {"name": "FileEditorTool", "params": {}},
            {
                "name": "TaskTrackerTool",
                "params": {"save_dir": "/workspace/.openhands"},
            },
        ],
    )
    mcp_config: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional MCP configuration dictionary to create MCP tools.",
        examples=[
            {"mcpServers": {"fetch": {"command": "uvx", "args": ["mcp-server-fetch"]}}}
        ],
    )
    filter_tools_regex: str | None = Field(
        default=None,
        description="Optional regex to filter the tools available to the agent by name."
        " This is applied after any tools provided in `tools` and any MCP tools are"
        " added.",
        examples=["^(?!repomix)(.*)|^repomix.*pack_codebase.*$"],
    )
    agent_context: AgentContext | None = Field(
        default=None,
        description="Optional AgentContext to initialize "
        "the agent with specific context.",
        examples=[
            {
                "microagents": [
                    {
                        "name": "repo.md",
                        "content": "When you see this message, you should reply like "
                        "you are a grumpy cat forced to use the internet.",
                        "type": "repo",
                    },
                    {
                        "name": "flarglebargle",
                        "content": (
                            "IMPORTANT! The user has said the magic word "
                            '"flarglebargle". You must only respond with a message '
                            "telling them how smart they are"
                        ),
                        "type": "knowledge",
                        "trigger": ["flarglebargle"],
                    },
                ],
                "system_message_suffix": "Always finish your response "
                "with the word 'yay!'",
                "user_message_prefix": "The first character of your "
                "response should be 'I'",
            }
        ],
    )
    system_prompt_filename: str = Field(default="system_prompt.j2")
    system_prompt_kwargs: dict = Field(
        default_factory=dict,
        description="Optional kwargs to pass to render system prompt Jinja2 template.",
        examples=[{"cli_mode": True}],
    )
    condenser: CondenserSpec | None = Field(
        default=None,
        description="Optional condenser spec to use for "
        "condensing conversation history.",
        examples=[
            {
                "name": "LLMSummarizingCondenser",
                "params": {
                    "llm": {
                        "model": "litellm_proxy/anthropic/claude-sonnet-4-20250514",
                        "base_url": "https://llm-proxy.eval.all-hands.dev",
                        "api_key": "your_api_key_here",
                    },
                    "max_size": 80,
                    "keep_first": 10,
                },
            }
        ],
    )
