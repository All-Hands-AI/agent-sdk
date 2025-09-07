from importlib.metadata import PackageNotFoundError, version

from openhands.sdk.agent import Agent, AgentBase
from openhands.sdk.context import AgentContext
from openhands.sdk.conversation import Conversation, ConversationCallbackType
from openhands.sdk.event import EventBase, EventType, LLMConvertibleEvent
from openhands.sdk.llm import (
    LLM,
    ImageContent,
    LLMRegistry,
    Message,
    RegistryEvent,
    TextContent,
)
from openhands.sdk.logger import get_logger
from openhands.sdk.mcp import MCPClient, MCPTool, create_mcp_tools
from openhands.sdk.tool import ActionBase, ObservationBase, Tool


try:
    __version__ = version("openhands.sdk")
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
    "AgentBase",
    "Agent",
    "ActionBase",
    "ObservationBase",
    "MCPClient",
    "MCPTool",
    "create_mcp_tools",
    "get_logger",
    "Conversation",
    "ConversationCallbackType",
    "EventType",
    "EventBase",
    "LLMConvertibleEvent",
    "AgentContext",
    "__version__",
]
