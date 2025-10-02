from abc import abstractmethod
from collections.abc import Sequence
from typing import Any, Literal

from litellm import ChatCompletionMessageToolCall
from litellm.types.utils import Message as LiteLLMMessage
from pydantic import BaseModel, ConfigDict, Field, field_validator

from openhands.sdk.logger import get_logger
from openhands.sdk.utils import DEFAULT_TEXT_CONTENT_LIMIT, maybe_truncate


logger = get_logger(__name__)


class ThinkingBlock(BaseModel):
    """Anthropic thinking block for extended thinking feature.

    This represents the raw thinking blocks returned by Anthropic models
    when extended thinking is enabled. These blocks must be preserved
    and passed back to the API for tool use scenarios.
    """

    type: Literal["thinking"] = "thinking"
    thinking: str = Field(..., description="The thinking content")
    signature: str = Field(
        ..., description="Cryptographic signature for the thinking block"
    )


class RedactedThinkingBlock(BaseModel):
    """Redacted thinking block for previous responses without extended thinking.

    This is used as a placeholder for assistant messages that were generated
    before extended thinking was enabled.
    """

    type: Literal["redacted_thinking"] = "redacted_thinking"
    data: str = Field(..., description="The redacted thinking content")


class BaseContent(BaseModel):
    cache_prompt: bool = False

    @abstractmethod
    def to_llm_dict(self) -> list[dict[str, str | dict[str, str]]]:
        """Convert to LLM API format. Always returns a list of dictionaries.

        Subclasses should implement this method to return a list of dictionaries,
        even if they only have a single item.
        """


class TextContent(BaseContent):
    type: Literal["text"] = "text"
    text: str
    # We use populate_by_name since mcp.types.TextContent
    # alias meta -> _meta, but .model_dumps() will output "meta"
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    def to_llm_dict(self) -> list[dict[str, str | dict[str, str]]]:
        """Convert to LLM API format."""
        text = self.text
        if len(text) > DEFAULT_TEXT_CONTENT_LIMIT:
            logger.warning(
                f"TextContent text length ({len(text)}) exceeds limit "
                f"({DEFAULT_TEXT_CONTENT_LIMIT}), truncating"
            )
            text = maybe_truncate(text, DEFAULT_TEXT_CONTENT_LIMIT)

        data: dict[str, str | dict[str, str]] = {
            "type": self.type,
            "text": text,
        }
        if self.cache_prompt:
            data["cache_control"] = {"type": "ephemeral"}
        return [data]


class ImageContent(BaseContent):
    type: Literal["image"] = "image"
    image_urls: list[str]

    def to_llm_dict(self) -> list[dict[str, str | dict[str, str]]]:
        """Convert to LLM API format."""
        images: list[dict[str, str | dict[str, str]]] = []
        for url in self.image_urls:
            images.append({"type": "image_url", "image_url": {"url": url}})
        if self.cache_prompt and images:
            images[-1]["cache_control"] = {"type": "ephemeral"}
        return images


class Message(BaseModel):
    # NOTE: this is not the same as EventSource
    # These are the roles in the LLM's APIs
    role: Literal["user", "system", "assistant", "tool"]
    content: Sequence[TextContent | ImageContent] = Field(default_factory=list)
    cache_enabled: bool = False
    vision_enabled: bool = False
    # function calling
    function_calling_enabled: bool = False
    # - tool calls (from LLM)
    tool_calls: list[ChatCompletionMessageToolCall] | None = None
    # - tool execution result (to LLM)
    tool_call_id: str | None = None
    name: str | None = None  # name of the tool
    # force string serializer
    force_string_serializer: bool = False
    # reasoning content (from reasoning models like o1, Claude thinking, DeepSeek R1)
    reasoning_content: str | None = Field(
        default=None,
        description="Intermediate reasoning/thinking content from reasoning models",
    )
    # Anthropic-specific thinking blocks (not normalized by LiteLLM)
    thinking_blocks: Sequence[ThinkingBlock | RedactedThinkingBlock] = Field(
        default_factory=list,
        description="Raw Anthropic thinking blocks for extended thinking feature",
    )

    @property
    def contains_image(self) -> bool:
        return any(isinstance(content, ImageContent) for content in self.content)

    @field_validator("content", mode="before")
    @classmethod
    def _coerce_content(cls, v: Any) -> Sequence[TextContent | ImageContent] | Any:
        # Accept None → []
        if v is None:
            return []
        # Accept a single string → [TextContent(...)]
        if isinstance(v, str):
            return [TextContent(text=v)]
        return v

    def to_llm_dict(self) -> dict[str, Any]:
        """Serialize message for LLM API consumption.

        This method chooses the appropriate serialization format based on the message
        configuration and provider capabilities:
        - String format: for providers that don't support list of content items
        - List format: for providers with vision/prompt caching/tool calls support
        """
        if not self.force_string_serializer and (
            self.cache_enabled or self.vision_enabled or self.function_calling_enabled
        ):
            message_dict = self._list_serializer()
        else:
            # some providers, like HF and Groq/llama, don't support a list here, but a
            # single string
            message_dict = self._string_serializer()

        return message_dict

    def _string_serializer(self) -> dict[str, Any]:
        # convert content to a single string
        content = "\n".join(
            item.text for item in self.content if isinstance(item, TextContent)
        )
        message_dict: dict[str, Any] = {"content": content, "role": self.role}

        # add tool call keys if we have a tool call or response
        return self._add_tool_call_keys(message_dict)

    def _list_serializer(self) -> dict[str, Any]:
        content: list[dict[str, Any]] = []
        role_tool_with_prompt_caching = False

        # Add thinking blocks first (for Anthropic extended thinking)
        # Only add thinking blocks for assistant messages
        if self.role == "assistant":
            thinking_blocks = list(
                self.thinking_blocks
            )  # Copy to avoid modifying original

            for thinking_block in thinking_blocks:
                thinking_dict = thinking_block.model_dump()
                content.append(thinking_dict)

        for item in self.content:
            # All content types now return list[dict[str, Any]]
            item_dicts = item.to_llm_dict()

            # We have to remove cache_prompt for tool content and move it up to the
            # message level
            # See discussion here for details: https://github.com/BerriAI/litellm/issues/6422#issuecomment-2438765472
            if self.role == "tool" and item.cache_prompt:
                role_tool_with_prompt_caching = True
                for d in item_dicts:
                    d.pop("cache_control", None)

            # Handle vision-enabled filtering for ImageContent
            if isinstance(item, ImageContent) and self.vision_enabled:
                content.extend(item_dicts)
            elif not isinstance(item, ImageContent):
                # Add non-image content (TextContent, etc.)
                content.extend(item_dicts)

        message_dict: dict[str, Any] = {"content": content, "role": self.role}
        if role_tool_with_prompt_caching:
            message_dict["cache_control"] = {"type": "ephemeral"}

        return self._add_tool_call_keys(message_dict)

    def _add_tool_call_keys(self, message_dict: dict[str, Any]) -> dict[str, Any]:
        """Add tool call keys if we have a tool call or response.

        NOTE: this is necessary for both native and non-native tool calling
        """
        # an assistant message calling a tool
        if self.tool_calls is not None:
            message_dict["tool_calls"] = [
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments,
                    },
                }
                for tool_call in self.tool_calls
            ]

        # an observation message with tool response
        if self.tool_call_id is not None:
            assert self.name is not None, (
                "name is required when tool_call_id is not None"
            )
            message_dict["tool_call_id"] = self.tool_call_id
            message_dict["name"] = self.name

        return message_dict

    @classmethod
    def from_litellm_message(cls, message: LiteLLMMessage) -> "Message":
        """Convert a LiteLLMMessage to our Message class.

        Provider-agnostic mapping for reasoning:
        - Prefer `message.reasoning_content` if present (LiteLLM normalized field)
        - Extract `thinking_blocks` from content array (Anthropic-specific)
        """
        assert message.role != "function", "Function role is not supported"

        rc = getattr(message, "reasoning_content", None)
        thinking_blocks = getattr(message, "thinking_blocks", None)
        # Convert to list of ThinkingBlock or RedactedThinkingBlock
        if thinking_blocks is not None:
            thinking_blocks = [
                ThinkingBlock(**tb)
                if tb.get("type") == "thinking"
                else RedactedThinkingBlock(**tb)
                for tb in thinking_blocks
            ]
        else:
            thinking_blocks = []

        return Message(
            role=message.role,
            content=[TextContent(text=message.content)]
            if isinstance(message.content, str)
            else [],
            tool_calls=message.tool_calls,
            reasoning_content=rc,
            thinking_blocks=thinking_blocks,
        )


def content_to_str(contents: Sequence[TextContent | ImageContent]) -> list[str]:
    """Convert a list of TextContent and ImageContent to a list of strings.

    This is primarily used for display purposes.
    """
    text_parts = []
    for content_item in contents:
        if isinstance(content_item, TextContent):
            text_parts.append(content_item.text)
        elif isinstance(content_item, ImageContent):
            text_parts.append(f"[Image: {len(content_item.image_urls)} URLs]")
    return text_parts
