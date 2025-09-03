from importlib.metadata import PackageNotFoundError, version

from .agent import AgentBase, CodeActAgent
from .config import LLMConfig, MCPConfig
from .conversation import Conversation, ConversationCallbackType
from .event import EventBase, EventType, LLMConvertibleEvent
from .llm import LLM, ImageContent, LLMRegistry, Message, RegistryEvent, TextContent
from .logger import get_logger
from .tool import ActionBase, ObservationBase, Tool


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
