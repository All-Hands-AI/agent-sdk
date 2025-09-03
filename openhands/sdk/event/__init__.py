from openhands.sdk.event.base import EventBase, LLMConvertibleEvent
from openhands.sdk.event.llm_convertible import (
    ActionEvent,
    AgentErrorEvent,
    MessageEvent,
    ObservationEvent,
    SystemPromptEvent,
)


EventType = (
    LLMConvertibleEvent
    | ActionEvent
    | ObservationEvent
    | MessageEvent
    | SystemPromptEvent
    | AgentErrorEvent
)

__all__ = [
    "EventBase",
    "LLMConvertibleEvent",
    "SystemPromptEvent",
    "ActionEvent",
    "ObservationEvent",
    "MessageEvent",
    "AgentErrorEvent",
    "EventType",
]
