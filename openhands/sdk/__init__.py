from importlib.metadata import PackageNotFoundError, version

from openhands.sdk.agent import Agent, AgentBase
from openhands.sdk.context import AgentContext
from openhands.sdk.context.condenser import (
    LLMSummarizingCondenser,
)
from openhands.sdk.conversation import (
    Conversation,
    ConversationCallbackType,
    ConversationType,
)
from openhands.sdk.event import EventBase, EventWithMetrics, LLMConvertibleEvent
from openhands.sdk.event.llm_convertible import MessageEvent
from openhands.sdk.io import FileStore, LocalFileStore
from openhands.sdk.llm import (
    LLM,
    ImageContent,
    LLMRegistry,
    Message,
    RegistryEvent,
    TextContent,
)
from openhands.sdk.logger import get_logger
from openhands.sdk.mcp import MCPClient, MCPTool, MCPToolObservation, create_mcp_tools
from openhands.sdk.tool import (
    ActionBase,
    ObservationBase,
    Tool,
    ToolBase,
    ToolSpec,
    list_registered_tools,
    register_tool,
    resolve_tool,
)


try:
    __version__ = version("openhands-sdk")
except PackageNotFoundError:
    __version__ = "0.0.0"  # fallback for editable/unbuilt environments

__all__ = [
    "LLM",
    "LLMRegistry",
    "RegistryEvent",
    "Message",
    "TextContent",
    "ImageContent",
    "Tool",
    "ToolBase",
    "ToolSpec",
    "AgentBase",
    "Agent",
    "ActionBase",
    "ObservationBase",
    "MCPClient",
    "MCPTool",
    "MCPToolObservation",
    "MessageEvent",
    "create_mcp_tools",
    "get_logger",
    "Conversation",
    "ConversationType",
    "ConversationCallbackType",
    "EventBase",
    "EventWithMetrics",
    "LLMConvertibleEvent",
    "AgentContext",
    "LLMSummarizingCondenser",
    "FileStore",
    "LocalFileStore",
    "register_tool",
    "resolve_tool",
    "list_registered_tools",
    "__version__",
]
