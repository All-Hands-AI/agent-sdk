from abc import abstractmethod
from collections.abc import Sequence
from typing import Any, Literal, cast

from litellm import ChatCompletionMessageToolCall
from litellm.types.completion import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionContentPartImageParam,
    ChatCompletionContentPartParam,
    ChatCompletionContentPartTextParam,
    ChatCompletionMessageParam,
    ChatCompletionMessageToolCallParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionToolMessageParam,
    ChatCompletionUserMessageParam,
)
from litellm.types.utils import Message as LiteLLMMessage
from pydantic import BaseModel, ConfigDict, Field, field_validator

from openhands.sdk.logger import get_logger
from openhands.sdk.utils import DEFAULT_TEXT_CONTENT_LIMIT, maybe_truncate


logger = get_logger(__name__)


class BaseContent(BaseModel):
    cache_prompt: bool = False

    @abstractmethod
    def to_llm_completion(self) -> Sequence[ChatCompletionContentPartParam]:
        """Serialize content parts for Chat Completions API (LiteLLM typed)."""


class TextContent(BaseContent):
    type: Literal["text"] = "text"
    text: str
    # We use populate_by_name since mcp.types.TextContent
    # alias meta -> _meta, but .model_dumps() will output "meta"
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    def to_llm_completion(self) -> Sequence[ChatCompletionContentPartTextParam]:
        """Serialize text content parts for Chat Completions API."""
        text = self.text
        if len(text) > DEFAULT_TEXT_CONTENT_LIMIT:
            logger.warning(
                f"TextContent text length ({len(text)}) exceeds limit "
                f"({DEFAULT_TEXT_CONTENT_LIMIT}), truncating"
            )
            text = maybe_truncate(text, DEFAULT_TEXT_CONTENT_LIMIT)

        data: ChatCompletionContentPartTextParam = {
            "type": "text",
            "text": text,
        }
        if self.cache_prompt:
            cast(dict[str, Any], data)["cache_control"] = {"type": "ephemeral"}
        return [data]


class ImageContent(BaseContent):
    type: Literal["image"] = "image"
    image_urls: list[str]

    def to_llm_completion(self) -> Sequence[ChatCompletionContentPartImageParam]:
        """Serialize image content parts for Chat Completions API."""
        images: list[ChatCompletionContentPartImageParam] = []
        for url in self.image_urls:
            i: ChatCompletionContentPartImageParam = {
                "type": "image_url",
                "image_url": {"url": url},
            }
            images.append(i)
        if self.cache_prompt and images:
            cast(dict[str, Any], images[-1])["cache_control"] = {"type": "ephemeral"}
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

    def to_llm_completion(self) -> ChatCompletionMessageParam:
        """Serialize message for Chat Completions API (LiteLLM typed payloads).

        - String format: for providers that don't support list of content items
        - List format: for providers with vision/prompt caching/tool calls support
        """
        if not self.force_string_serializer and (
            self.cache_enabled or self.vision_enabled or self.function_calling_enabled
        ):
            return self._list_serializer()
        else:
            # some providers, like HF and Groq/llama, don't support a list here, but a
            # single string
            return self._string_serializer()

    def _string_serializer(self) -> ChatCompletionMessageParam:
        text = "\n".join(
            item.text for item in self.content if isinstance(item, TextContent)
        )
        if self.role == "system":
            sys_msg: ChatCompletionSystemMessageParam = {
                "role": "system",
                "content": text,
            }
            return sys_msg
        if self.role == "user":
            user_msg: ChatCompletionUserMessageParam = {"role": "user", "content": text}
            return user_msg
        if self.role == "assistant":
            if self.tool_calls is not None:
                tool_calls: list[ChatCompletionMessageToolCallParam] = []
                for tc in self.tool_calls:
                    fn = tc.function
                    name = fn.name
                    arguments = fn.arguments
                    assert isinstance(name, str)
                    assert isinstance(arguments, str)
                    tool_calls.append(
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": name,
                                "arguments": arguments,
                            },
                        }
                    )
                assistant_msg: ChatCompletionAssistantMessageParam = {
                    "role": "assistant"
                }
                if text:
                    assistant_msg["content"] = text
                assistant_msg["tool_calls"] = tool_calls
                return assistant_msg
            assistant_msg: ChatCompletionAssistantMessageParam = {"role": "assistant"}
            if text:
                assistant_msg["content"] = text
            return assistant_msg
        if self.role == "tool":
            assert self.tool_call_id is not None, "tool messages require tool_call_id"
            tool_msg: ChatCompletionToolMessageParam = {
                "role": "tool",
                "content": text,
                "tool_call_id": self.tool_call_id,
            }
            return tool_msg
        raise AssertionError(f"Unsupported role: {self.role}")

    def _list_serializer(self) -> ChatCompletionMessageParam:
        parts: list[ChatCompletionContentPartParam] = []
        role_tool_with_prompt_caching = False

        # Build typed content parts directly from Message content
        for item in self.content:
            if isinstance(item, TextContent):
                txt = item.text
                if len(txt) > DEFAULT_TEXT_CONTENT_LIMIT:
                    txt = maybe_truncate(txt, DEFAULT_TEXT_CONTENT_LIMIT)
                t: ChatCompletionContentPartTextParam = {"type": "text", "text": txt}
                if self.role == "tool" and item.cache_prompt:
                    role_tool_with_prompt_caching = True
                parts.append(t)
            elif isinstance(item, ImageContent) and self.vision_enabled:
                if self.role == "tool" and item.cache_prompt:
                    role_tool_with_prompt_caching = True
                for url in item.image_urls:
                    i: ChatCompletionContentPartImageParam = {
                        "type": "image_url",
                        "image_url": {"url": url},
                    }
                    parts.append(i)

        # Build a string-only variant from text parts as fallback when no parts
        text_only = "\n".join(
            (
                maybe_truncate(c.text, DEFAULT_TEXT_CONTENT_LIMIT)
                if len(c.text) > DEFAULT_TEXT_CONTENT_LIMIT
                else c.text
            )
            for c in self.content
            if isinstance(c, TextContent)
        )

        if self.role == "system":
            sys_msg: ChatCompletionSystemMessageParam = {
                "role": "system",
                "content": text_only,
            }
            return sys_msg
        if self.role == "user":
            user_msg: ChatCompletionUserMessageParam = {
                "role": "user",
                "content": parts if parts else text_only,
            }
            return user_msg
        if self.role == "assistant":
            if self.tool_calls is not None:
                tool_calls: list[ChatCompletionMessageToolCallParam] = []
                for tc in self.tool_calls:
                    fn = tc.function
                    name = fn.name
                    arguments = fn.arguments
                    assert isinstance(name, str)
                    assert isinstance(arguments, str)
                    tool_calls.append(
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": name,
                                "arguments": arguments,
                            },
                        }
                    )
                assistant_msg: ChatCompletionAssistantMessageParam = {
                    "role": "assistant"
                }
                if text_only:
                    assistant_msg["content"] = text_only
                assistant_msg["tool_calls"] = tool_calls
                return assistant_msg
            assistant_msg: ChatCompletionAssistantMessageParam = {"role": "assistant"}
            if text_only:
                assistant_msg["content"] = text_only
            return assistant_msg
        if self.role == "tool":
            assert self.tool_call_id is not None, "tool messages require tool_call_id"
            msg: ChatCompletionToolMessageParam = {
                "role": "tool",
                "content": parts if parts else text_only,
                "tool_call_id": self.tool_call_id,
            }
            if role_tool_with_prompt_caching:
                # extra field grafted at the message level
                cast(dict[str, Any], msg)["cache_control"] = {"type": "ephemeral"}
            return msg
        raise AssertionError(f"Unsupported role: {self.role}")

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
        """
        assert message.role != "function", "Function role is not supported"

        rc = getattr(message, "reasoning_content", None)

        return Message(
            role=message.role,
            content=[TextContent(text=message.content)]
            if isinstance(message.content, str)
            else [],
            tool_calls=message.tool_calls,
            reasoning_content=rc,
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
