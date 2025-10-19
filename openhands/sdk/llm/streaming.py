from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal


StreamChannel = Literal[
    "assistant_message",
    "reasoning_summary",
    "function_call_arguments",
    "tool_call_output",
    "refusal",
    "system",
    "status",
    "unknown",
]


@dataclass(slots=True)
class LLMStreamEvent:
    """Represents a streaming delta emitted by an LLM provider."""

    type: str
    channel: StreamChannel = "unknown"
    text: str | None = None
    arguments: str | None = None
    output_index: int | None = None
    content_index: int | None = None
    item_id: str | None = None
    is_final: bool = False
    raw: Any | None = None


TokenCallbackType = Callable[[LLMStreamEvent], None]
