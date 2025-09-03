from openhands.core.event.context import Condensation, CondensationRequest

from .base import EventBase, LLMConvertibleEvent
from .llm_convertible import (
    ActionEvent,
    AgentErrorEvent,
    MessageEvent,
    ObservationEvent,
    SystemPromptEvent,
)


EventType = LLMConvertibleEvent | ActionEvent | ObservationEvent | MessageEvent | SystemPromptEvent | AgentErrorEvent | Condensation | CondensationRequest


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
