import importlib.util

from openhands.sdk.agent.agent import Agent
from openhands.sdk.agent.base import AgentBase
from openhands.sdk.agent.spec import AgentSpec


__all__ = [
    "Agent",
    "AgentBase",
    "AgentSpec",
]

# Conditionally import ClaudeCodeAgent if claude-code-sdk is available
if importlib.util.find_spec("claude_code_sdk") is not None:
    from openhands.sdk.agent.claude_code_agent import ClaudeCodeAgent  # noqa: F401

    __all__.append("ClaudeCodeAgent")
