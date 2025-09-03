from importlib.metadata import PackageNotFoundError, version

from openhands.core.agent import AgentBase, CodeActAgent
from openhands.core.config import LLMConfig, MCPConfig
from openhands.core.conversation import Conversation, ConversationCallbackType
from openhands.core.event import EventBase, EventType, LLMConvertibleEvent
from openhands.core.llm import (
    LLM,
    ImageContent,
    LLMRegistry,
    Message,
    RegistryEvent,
    TextContent,
)
from openhands.core.logger import get_logger
from openhands.core.tool import ActionBase, ObservationBase, Tool


try:
    __version__ = version("openhands-core")
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
    "CodeActAgent",
    "ActionBase",
    "ObservationBase",
    "LLMConfig",
    "MCPConfig",
    "get_logger",
    "Conversation",
    "ConversationCallbackType",
    "EventType",
    "EventBase",
    "LLMConvertibleEvent",
    "__version__",
]
