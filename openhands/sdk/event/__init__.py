from openhands.sdk.event.base import EventBase, LLMConvertibleEvent
from openhands.sdk.event.condenser import Condensation, CondensationRequest
from openhands.sdk.event.llm_convertible import (
    ActionEvent,
    AgentErrorEvent,
    MessageEvent,
    ObservationEvent,
    PauseEvent,
    SystemPromptEvent,
    UserRejectObservation,
)


EventType = (
    LLMConvertibleEvent
    | ActionEvent
    | ObservationEvent
    | MessageEvent
    | SystemPromptEvent
    | AgentErrorEvent
    | UserRejectObservation
    | PauseEvent
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
    "UserRejectObservation",
    "PauseEvent",
    "EventType",
    "Condensation",
    "CondensationRequest",
]
