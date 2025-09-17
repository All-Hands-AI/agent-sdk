"""Type annotations for serialization / deserialization"""

from typing import TYPE_CHECKING

from openhands.sdk.event.base import EventBase
from openhands.sdk.event.condenser import (
    Condensation,
    CondensationRequest,
    CondensationSummaryEvent,
)
from openhands.sdk.event.llm_convertible import (
    ActionEvent,
    AgentErrorEvent,
    MessageEvent,
    ObservationEvent,
    SystemPromptEvent,
    UserRejectObservation,
)
from openhands.sdk.event.user_action import PauseEvent
from openhands.sdk.utils.pydantic_utils import discriminated_union


if TYPE_CHECKING:
    Event = EventBase
else:
    Event = discriminated_union(
        AgentErrorEvent,
        ActionEvent,
        Condensation,
        CondensationRequest,
        CondensationSummaryEvent,
        MessageEvent,
        ObservationEvent,
        PauseEvent,
        SystemPromptEvent,
        UserRejectObservation,
    )
