import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from openhands.core.llm import Message, TextContent

from .types import SourceType


if TYPE_CHECKING:
    from .llm_convertible import ActionEvent


class EventBase(BaseModel, ABC):
    """Base class for all events: timestamped envelope with media."""
    model_config = ConfigDict(extra="forbid")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique event id (ULID/UUID)")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat(), description="Event timestamp") # consistent with V1
    source: SourceType = Field(..., description="The source of this event")

class LLMConvertibleEvent(EventBase, ABC):
    """Base class for events that can be converted to LLM messages."""
    @abstractmethod
    def to_llm_message(self) -> Message:
        raise NotImplementedError()
    
    @staticmethod
    def events_to_messages(events: list["LLMConvertibleEvent"]) -> list[Message]:
        """Convert event stream to LLM message stream, handling multi-action batches"""
        from .llm_convertible import ActionEvent  # Import here to avoid circular import
        
        messages = []
        i = 0
        
        while i < len(events):
            event = events[i]
            
            if isinstance(event, ActionEvent):
                # Collect all ActionEvents from same LLM batch
                batch_events: list[ActionEvent] = [event]
                batch_id = event.llm_batch_id
                
                # Look ahead for related events
                j = i + 1
                while (j < len(events) and 
                       isinstance(events[j], ActionEvent) and 
                       hasattr(events[j], 'llm_batch_id') and
                       events[j].llm_batch_id == batch_id):  # type: ignore
                    batch_events.append(events[j])  # type: ignore
                    j += 1
                
                # Create combined message for the batch
                messages.append(_combine_action_events(batch_events))
                i = j
            else:
                # Regular event - direct conversion
                messages.append(event.to_llm_message())
                i += 1
                
        return messages


def _combine_action_events(events: list["ActionEvent"]) -> Message:
    """Combine multiple ActionEvents into single LLM message"""
    from typing import cast

    from openhands.core.llm import ImageContent
    
    if len(events) == 1:
        return events[0].to_llm_message()
    
    # Multi-action case - reconstruct original LLM response
    all_tool_calls = [event._action_to_tool_call() for event in events]
    content: list[TextContent | ImageContent] = cast(list[TextContent | ImageContent], events[0].thought)
    return Message(
        role="assistant",
        content=content,  # Shared thought content
        tool_calls=all_tool_calls
    )

