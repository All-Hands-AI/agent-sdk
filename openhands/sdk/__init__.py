from importlib.metadata import PackageNotFoundError, version

from openhands.sdk.agent import Agent, AgentBase, AgentSpec
from openhands.sdk.context import AgentContext
from openhands.sdk.context.condenser import (
    Condenser,
    LLMSummarizingCondenser,
)
from openhands.sdk.conversation import Conversation, ConversationCallbackType
from openhands.sdk.event import Event, EventBase, EventWithMetrics, LLMConvertibleEvent
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
from openhands.sdk.tool import ActionBase, ObservationBase, Tool, ToolSpec


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
    "ToolSpec",
    "AgentBase",
    "Agent",
    "AgentSpec",
    "ActionBase",
    "ObservationBase",
    "MCPClient",
    "MCPTool",
    "MCPToolObservation",
    "create_mcp_tools",
    "get_logger",
    "Conversation",
    "ConversationCallbackType",
    "Event",
    "EventBase",
    "EventWithMetrics",
    "LLMConvertibleEvent",
    "AgentContext",
    "Condenser",
    "LLMSummarizingCondenser",
    "FileStore",
    "LocalFileStore",
    "__version__",
]
