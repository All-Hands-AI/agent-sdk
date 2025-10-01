"""OpenHands runtime package."""

from openhands.sdk.tool.builtins import BUILT_IN_TOOLS, FinishTool, ThinkTool
from openhands.sdk.tool.registry import (
    list_registered_tools,
    register_tool,
    resolve_tool,
)
from openhands.sdk.tool.schema import (
    ActionBase,
    ObservationBase,
)
from openhands.sdk.tool.spec import ToolSpec
from openhands.sdk.tool.tool import (
    ExecutableTool,
    Tool,
    ToolAnnotations,
    ToolBase,
    ToolDefinition,
    ToolExecutor,
)


# Backward compatibility alias
ToolDefinitionExecutor = ToolExecutor


__all__ = [
    "Tool",
    "ToolDefinition",
    "ToolBase",
    "ToolSpec",
    "ToolAnnotations",
    "ToolExecutor",
    "ToolDefinitionExecutor",
    "ExecutableTool",
    "ActionBase",
    "ObservationBase",
    "FinishTool",
    "ThinkTool",
    "BUILT_IN_TOOLS",
    "register_tool",
    "resolve_tool",
    "list_registered_tools",
]
