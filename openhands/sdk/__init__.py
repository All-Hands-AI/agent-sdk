import warnings
from importlib.metadata import PackageNotFoundError, version

from openhands.sdk.agent import Agent, AgentBase
from openhands.sdk.context import AgentContext
from openhands.sdk.context.condenser import (
    LLMSummarizingCondenser,
)
from openhands.sdk.conversation import (
    BaseConversation,
    Conversation,
    ConversationCallbackType,
    LocalConversation,
    RemoteConversation,
)
from openhands.sdk.conversation.conversation_stats import ConversationStats
from openhands.sdk.event import Event, LLMConvertibleEvent
from openhands.sdk.event.llm_convertible import MessageEvent
from openhands.sdk.io import FileStore, LocalFileStore
from openhands.sdk.llm import (
    LLM,
    ImageContent,
    LLMRegistry,
    Message,
    RedactedThinkingBlock,
    RegistryEvent,
    TextContent,
    ThinkingBlock,
)
from openhands.sdk.logger import get_logger
from openhands.sdk.mcp import (
    MCPClient,
    MCPToolDefinition,
    MCPToolObservation,
    create_mcp_tools,
)
from openhands.sdk.tool import (
    Action,
    Observation,
    Tool,
    ToolBase,
    ToolDefinition,
    list_registered_tools,
    register_tool,
    resolve_tool,
)
from openhands.sdk.workspace import (
    LocalWorkspace,
    RemoteWorkspace,
    Workspace,
)


def _suppress_litellm_pydantic_warnings(
    message, category, filename, lineno, file=None, line=None
):
    """
    Global warning filter to suppress LiteLLM Pydantic serialization warnings
    LiteLLM's Message and StreamingChoices objects cause Pydantic serialization warnings
    when they are serialized because they have fewer fields than expected by the
    Pydantic model definitions. These warnings are harmless but noisy, appearing as:
      "PydanticSerializationUnexpectedValue(Expected 10 fields but got 7: Expected..."
      "PydanticSerializationUnexpectedValue(Expected `StreamingChoices`..."

    This filter suppresses only these specific warnings while preserving all other
    Pydantic warnings that might indicate legitimate issues in the codebase.
    """
    if (
        category is UserWarning
        and filename.endswith("pydantic/main.py")
        and isinstance(message, Warning)
    ):
        msg_str = str(message)
        # Check if this is a LiteLLM-related serialization warning
        if "PydanticSerializationUnexpectedValue" in msg_str and (
            "Expected `Message`" in msg_str or "Expected `StreamingChoices`" in msg_str
        ):
            return  # Suppress this warning
    # Show all other warnings
    _original_showwarning(message, category, filename, lineno, file, line)


# Install the global warning filter
_original_showwarning = warnings.showwarning
warnings.showwarning = _suppress_litellm_pydantic_warnings


try:
    __version__ = version("openhands-sdk")
except PackageNotFoundError:
    __version__ = "0.0.0"  # fallback for editable/unbuilt environments

__all__ = [
    "LLM",
    "LLMRegistry",
    "ConversationStats",
    "RegistryEvent",
    "Message",
    "TextContent",
    "ImageContent",
    "ThinkingBlock",
    "RedactedThinkingBlock",
    "Tool",
    "ToolDefinition",
    "ToolBase",
    "AgentBase",
    "Agent",
    "Action",
    "Observation",
    "MCPClient",
    "MCPToolDefinition",
    "MCPToolObservation",
    "MessageEvent",
    "create_mcp_tools",
    "get_logger",
    "Conversation",
    "BaseConversation",
    "LocalConversation",
    "RemoteConversation",
    "ConversationCallbackType",
    "Event",
    "LLMConvertibleEvent",
    "AgentContext",
    "LLMSummarizingCondenser",
    "FileStore",
    "LocalFileStore",
    "register_tool",
    "resolve_tool",
    "list_registered_tools",
    "Workspace",
    "LocalWorkspace",
    "RemoteWorkspace",
    "__version__",
]
