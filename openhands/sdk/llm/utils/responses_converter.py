"""Utilities for converting between ChatCompletions and Responses API formats."""

from typing import Any

from litellm.types.utils import ModelResponse

from openhands.sdk.llm.message import Message


def messages_to_responses_input(
    messages: list[dict[str, Any]] | list[Message],
) -> str:
    """Convert ChatCompletions messages format to Responses API input string.

    The Responses API uses a simple string input instead of the structured
    messages array used by ChatCompletions. This function converts the
    messages to a single string that captures the conversation context.

    Args:
        messages: List of messages in ChatCompletions format

    Returns:
        String input suitable for Responses API
    """
    if not messages:
        return ""

    # Convert Message objects to dicts if needed
    dict_messages: list[dict[str, Any]]
    if messages and isinstance(messages[0], Message):
        # Format messages directly to avoid circular import
        dict_messages = []
        for message in messages:
            if isinstance(message, Message):
                # Set basic capabilities for formatting
                message.cache_enabled = False
                message.vision_enabled = False
                message.function_calling_enabled = False
                dict_messages.append(message.to_llm_dict())
            else:
                dict_messages.append(message)
    else:
        dict_messages = messages  # type: ignore[assignment]

    # Convert messages to a single input string
    input_parts = []

    for msg in dict_messages:
        role = msg.get("role", "")
        content = msg.get("content", "")

        if role == "system":
            input_parts.append(f"System: {content}")
        elif role == "user":
            input_parts.append(f"User: {content}")
        elif role == "assistant":
            input_parts.append(f"Assistant: {content}")
        elif role == "tool":
            # Tool responses are included as context
            tool_call_id = msg.get("tool_call_id", "")
            input_parts.append(f"Tool Result ({tool_call_id}): {content}")

    return "\n\n".join(input_parts)


def responses_to_completion_format(
    responses_result: Any,
) -> ModelResponse:
    """Convert Responses API result to ChatCompletions format.

    This allows the Responses API result to be used with existing code
    that expects ChatCompletions format.

    Args:
        responses_result: Result from litellm.responses()

    Returns:
        ModelResponse in ChatCompletions format
    """
    # Extract the main content and reasoning content if available
    output_items = getattr(responses_result, "output", [])

    content = ""
    reasoning_content = ""

    for item in output_items:
        if hasattr(item, "type"):
            if item.type == "message":
                if hasattr(item, "content") and hasattr(item.content, "text"):
                    content = item.content.text
            elif item.type == "reasoning":
                if hasattr(item, "content"):
                    reasoning_content = item.content

    # Create a ChatCompletions-compatible response
    message = {
        "role": "assistant",
        "content": content,
    }

    # Add reasoning content as a custom field if available
    if reasoning_content:
        message["reasoning_content"] = reasoning_content

    # Build the response structure
    response = {
        "id": responses_result.id,  # Always present in ResponsesAPIResponse
        "object": "chat.completion",
        "created": getattr(
            responses_result, "created_at", 0
        ),  # Fixed: field is 'created_at', not 'created'
        "model": getattr(
            responses_result, "model", ""
        ),  # Keep getattr: model can be None
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
    }

    # Extract usage information if available
    if hasattr(responses_result, "usage"):
        usage = responses_result.usage
        response["usage"]["prompt_tokens"] = usage.input_tokens
        response["usage"]["completion_tokens"] = usage.output_tokens
        response["usage"]["total_tokens"] = usage.total_tokens

    return ModelResponse(**response)
