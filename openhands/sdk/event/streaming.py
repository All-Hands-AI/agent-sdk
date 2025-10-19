from __future__ import annotations

from pydantic import Field
from rich.text import Text

from openhands.sdk.event.base import Event
from openhands.sdk.event.types import SourceType
from openhands.sdk.llm.streaming import LLMStreamEvent, StreamChannel


class StreamingDeltaEvent(Event):
    """Event emitted for each incremental LLM streaming delta."""

    source: SourceType = Field(default="agent")
    stream_event: LLMStreamEvent

    @property
    def channel(self) -> StreamChannel:
        return self.stream_event.channel

    @property
    def visualize(self) -> Text:
        content = Text()
        content.append(f"Channel: {self.stream_event.channel}\n", style="bold")

        if self.stream_event.text:
            content.append(self.stream_event.text)
        elif self.stream_event.arguments:
            content.append(self.stream_event.arguments)
        else:
            content.append("[no streaming content]")

        return content
