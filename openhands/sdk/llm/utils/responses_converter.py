"""Utilities for converting Responses API results into Chat Completions format."""

from typing import Any

from litellm.types.llms.openai import ResponsesAPIResponse
from litellm.types.responses.main import (
    GenericResponseOutputItem,
    OutputFunctionToolCall,
    OutputText,
)
from litellm.types.utils import ModelResponse
from openai.types.responses.response_function_tool_call import ResponseFunctionToolCall
from openai.types.responses.response_output_message import ResponseOutputMessage
from openai.types.responses.response_output_refusal import ResponseOutputRefusal
from openai.types.responses.response_output_text import ResponseOutputText
from openai.types.responses.response_reasoning_item import ResponseReasoningItem

from openhands.sdk.logger import get_logger


logger = get_logger(__name__)


def messages_to_responses_items(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert Chat Completions-style messages into Responses API input items.

    Mapping rules:
    - user/system/assistant text -> {type: 'message', role, content}
    - assistant tool_calls -> for each call ->
      {type: 'function_call', call_id, name, arguments}
    - tool messages -> {type: 'function_call_output', call_id: tool_call_id, output}
    """
    if not messages:
        return []

    dict_messages = messages

    def _to_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for seg in content:
                if isinstance(seg, dict):
                    t = seg.get("text")
                    if isinstance(t, str) and t:
                        parts.append(t)
            return "".join(parts)
        return str(content) if content is not None else ""

    out: list[dict[str, Any]] = []
    for msg in dict_messages:
        role = str(msg.get("role", ""))
        # 1) Tool outputs -> function_call_output items
        if role == "tool":
            try:
                call_id = str(msg["tool_call_id"])  # Chat Completions tool message key
                output_text = _to_text(msg.get("content", ""))
                if output_text is not None:
                    out.append(
                        {
                            "type": "function_call_output",
                            "call_id": call_id,
                            "output": output_text,
                        }
                    )
            except Exception as e:
                logger.debug(
                    f"Skipping malformed tool output message: {msg!r}; error: {e}"
                )
            continue

        # 2) Assistant with tool_calls -> function_call items (and optional text)
        if role == "assistant" and isinstance(msg.get("tool_calls"), list):
            # Put assistant text before tool_calls to satisfy ordering
            text = _to_text(msg.get("content", ""))
            if text:
                out.append({"role": "assistant", "content": text})
            tool_calls = msg.get("tool_calls") or []
            for tc in tool_calls:
                try:
                    fn = tc.get("function")
                    out.append(
                        {
                            "type": "function_call",
                            "call_id": str(tc.get("id")),
                            "name": str(fn.get("name")),
                            "arguments": str(fn.get("arguments")),
                        }
                    )
                except Exception as e:
                    logger.debug(f"Skipping malformed tool_call: {tc!r}; error: {e}")
                    pass
            continue

        # 3) Plain text messages
        text = _to_text(msg.get("content", ""))
        if role in {"user", "system", "assistant", "developer"} and text:
            out.append({"role": role, "content": text})
        else:
            if text:
                out.append({"role": "user", "content": text})
    return out


def responses_to_completion_format(
    responses_result: ResponsesAPIResponse,
) -> ModelResponse:
    """Convert Responses API result to ChatCompletions format.

    This allows the Responses API result to be used with existing code
    that expects ChatCompletions format.

    Args:
        responses_result: Result from litellm.responses()

    Returns:
        ModelResponse in ChatCompletions format
    """
    # Extract the main content, tool calls, and reasoning content if available
    output_items = responses_result.output

    content = ""
    reasoning_content = ""
    tool_calls: list[dict[str, Any]] = []

    for item in output_items:
        # Strict typed mapping based on LiteLLM/OpenAI response classes
        if isinstance(item, ResponseOutputMessage) and item.type == "message":
            for seg in item.content:
                if isinstance(seg, ResponseOutputText) and seg.text:
                    content = seg.text
                elif isinstance(seg, ResponseOutputRefusal):
                    pass
            continue
        if isinstance(item, ResponseFunctionToolCall) and item.type == "function_call":
            tool_calls.append(
                {
                    "id": (item.call_id or item.id or ""),
                    "type": "function",
                    "function": {"name": item.name, "arguments": item.arguments},
                }
            )
            continue
        if isinstance(item, GenericResponseOutputItem) and item.type == "message":
            for seg in item.content:
                if isinstance(seg, OutputText) and seg.text:
                    content = seg.text
            continue
        if isinstance(item, OutputFunctionToolCall) and item.type == "function_call":
            tool_calls.append(
                {
                    "id": (item.call_id or item.id or ""),
                    "type": "function",
                    "function": {"name": item.name, "arguments": item.arguments},
                }
            )
            continue
        if isinstance(item, ResponseReasoningItem) and item.type == "reasoning":
            if item.content:
                parts = [seg.text for seg in item.content if seg.text]
                if parts:
                    reasoning_content = "\n\n".join(parts)
            elif item.summary:
                parts = [s.text for s in item.summary if s.text]
                if parts:
                    reasoning_content = "\n\n".join(parts)

    # Create a ChatCompletions-compatible response
    message: dict[str, Any] = {
        "role": "assistant",
        "content": content,
    }
    if tool_calls:
        message["tool_calls"] = tool_calls

    # Add reasoning content as a custom field if available
    if reasoning_content:
        message["reasoning_content"] = reasoning_content

    # model string
    model = responses_result.model

    finish_reason = "tool_calls" if tool_calls else "stop"

    response = {
        "id": responses_result.id,
        "object": "chat.completion",
        "created": int(responses_result.created_at),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": finish_reason,
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
    }

    # Extract usage information if available
    if hasattr(responses_result, "usage") and responses_result.usage is not None:
        usage = responses_result.usage
        # Map Responses API usage fields to ChatCompletions format
        response["usage"]["prompt_tokens"] = getattr(usage, "input_tokens", 0)
        response["usage"]["completion_tokens"] = getattr(usage, "output_tokens", 0)
        response["usage"]["total_tokens"] = getattr(usage, "total_tokens", 0)

        # Map reasoning tokens if available
        output_details = getattr(usage, "output_tokens_details", None)
        if output_details and hasattr(output_details, "reasoning_tokens"):
            reasoning_tokens = getattr(output_details, "reasoning_tokens", None)
            if reasoning_tokens is not None and isinstance(reasoning_tokens, int):
                response["usage"]["completion_tokens_details"] = {
                    "reasoning_tokens": reasoning_tokens
                }

    return ModelResponse(**response)
