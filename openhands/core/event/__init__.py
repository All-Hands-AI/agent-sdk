from openhands.core.event.base import EventBase, LLMConvertibleEvent
from openhands.core.event.llm_convertible import (
    ActionEvent,
    AgentErrorEvent,
    MessageEvent,
    ObservationEvent,
    SystemPromptEvent,
    UserRejectsObservation,
)


EventType = (
    LLMConvertibleEvent
    | ActionEvent
    | ObservationEvent
    | MessageEvent
    | SystemPromptEvent
    | AgentErrorEvent
    | UserRejectsObservation
)

__all__ = [
    "EventBase",
    "LLMConvertibleEvent",
    "SystemPromptEvent",
    "ActionEvent",
    "ObservationEvent",
    "MessageEvent",
    "AgentErrorEvent",
    "UserRejectsObservation",
    "EventType",
]
