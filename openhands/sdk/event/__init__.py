from openhands.sdk.event.base import EventBase, LLMConvertibleEvent
from openhands.sdk.event.condenser import Condensation, CondensationRequest
from openhands.sdk.event.llm_convertible import (
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
    | Condensation
    | CondensationRequest
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
    "Condensation",
    "CondensationRequest",
]
