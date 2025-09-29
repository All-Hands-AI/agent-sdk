"""Events related to conversation state updates."""

import uuid

from pydantic import BaseModel, Field, field_validator

from openhands.sdk.conversation.state import ConversationState
from openhands.sdk.event.base import EventBase
from openhands.sdk.event.types import SourceType


class ConversationStateUpdateEvent(EventBase):
    """Event that contains conversation state updates.

    This event is sent via websocket whenever the conversation state changes,
    allowing remote clients to stay in sync without making REST API calls.

    All fields are serialized versions of the corresponding ConversationState fields
    to ensure compatibility with websocket transmission.
    """

    source: SourceType = "environment"
    key: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique key for this state update event",
    )
    value: dict = Field(
        default_factory=dict,
        description="Serialized conversation state updates",
    )

    @field_validator("key")
    def validate_key(cls, key):
        if not isinstance(key, str):
            raise ValueError("Key must be a string")
        valid_keys = ConversationState.model_fields.keys()
        if key not in valid_keys:
            raise ValueError(f"Invalid key: {key}. Must be one of {list(valid_keys)}")
        return key

    @field_validator("value")
    def validate_value(cls, value, info):
        key = info.data.get("key")
        if key is None:
            raise ValueError("Key must be set before validating value")
        field_info = ConversationState.model_fields.get(key)
        if field_info is None:
            raise ValueError(f"Invalid key: {key}")

        if field_info.annotation is None:
            # No type annotation, skip validation
            pass
        elif field_info.annotation in {int, str, bool, float, list, dict}:
            # Primitive types can be directly validated
            field_info.annotation(value)
        elif issubclass(field_info.annotation, BaseModel):
            field_info.annotation.model_validate(value)
        return value

    def __str__(self) -> str:
        return f"ConversationStateUpdate(key={self.key}, value={self.value})"
