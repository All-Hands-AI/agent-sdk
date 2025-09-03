"""Implementing essential tools that doesn't interact with the environment.

These are built in and are *required* for the agent to work.

For tools that require interacting with the environment, add them to `openhands/tools`.
"""

from openhands.sdk.tool.builtins.finish import (
    FinishAction,
    FinishObservation,
    FinishTool,
)


BUILT_IN_TOOLS = [FinishTool]

__all__ = [
    "BUILT_IN_TOOLS",
    "FinishTool",
    "FinishAction",
    "FinishObservation",
]
