import copy

from pydantic import ConfigDict, Field
from rich.text import Text

from openhands.sdk.event.base import N_CHAR_PREVIEW, LLMConvertibleEvent
from openhands.sdk.event.types import SourceType
from openhands.sdk.llm import ImageContent, Message, TextContent, content_to_str


class MessageEvent(LLMConvertibleEvent):
    """Message from either agent or user.

    This is originally the "MessageAction", but it suppose not to be tool call."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: SourceType
    llm_message: Message = Field(
        ..., description="The exact LLM message for this message event"
    )

    # context extensions stuff / microagent can go here
    activated_microagents: list[str] = Field(
        default_factory=list, description="List of activated microagent name"
    )
    extended_content: list[TextContent] = Field(
        default_factory=list, description="List of content added by agent context"
    )

    @property
    def reasoning_content(self) -> str:
        return self.llm_message.reasoning_content or ""

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation of this message event."""
        content = Text()

        text_parts = content_to_str(self.llm_message.content)
        if text_parts:
            full_content = "".join(text_parts)
            content.append(full_content)
        else:
            content.append("[no text content]")

        # Add microagent information if present
        if self.activated_microagents:
            content.append(
                f"\nActivated Microagents: {', '.join(self.activated_microagents)}",
            )

        # Add extended content if available
        if self.extended_content:
            assert not any(
                isinstance(c, ImageContent) for c in self.extended_content
            ), "Extended content should not contain images"
            text_parts = content_to_str(self.extended_content)
            content.append("\nPrompt Extension based on Agent Context:\n")
            content.append(" ".join(text_parts))

        return content

    def to_llm_message(self) -> Message:
        msg = copy.deepcopy(self.llm_message)
        msg.content = list(msg.content) + list(self.extended_content)
        return msg

    def __str__(self) -> str:
        """Plain text string representation for MessageEvent."""
        base_str = f"{self.__class__.__name__} ({self.source})"
        # Extract text content from the message
        text_parts = []
        message = self.to_llm_message()
        for content in message.content:
            if isinstance(content, TextContent):
                text_parts.append(content.text)
            elif isinstance(content, ImageContent):
                text_parts.append(f"[Image: {len(content.image_urls)} URLs]")

        if text_parts:
            content_preview = " ".join(text_parts)
            if len(content_preview) > N_CHAR_PREVIEW:
                content_preview = content_preview[: N_CHAR_PREVIEW - 3] + "..."
            microagent_info = (
                f" [Microagents: {', '.join(self.activated_microagents)}]"
                if self.activated_microagents
                else ""
            )
            return f"{base_str}\n  {message.role}: {content_preview}{microagent_info}"
        else:
            return f"{base_str}\n  {message.role}: [no text content]"
