from openhands.core.event.base import EventBase
from openhands.core.event.types import SourceType


class Condensation(EventBase):
    """This action indicates a condensation of the conversation history is happening.

    There are two ways to specify the events to be forgotten:
    1. By providing a list of event IDs.
    2. By providing the start and end IDs of a range of events.

    In the second case, we assume that event IDs are monotonically increasing, and that _all_ events between the start and end IDs are to be forgotten.

    Raises:
        ValueError: If the optional fields are not instantiated in a valid configuration.
    """
    
    forgotten_event_ids: list[str] | None = None
    """The IDs of the events that are being forgotten (removed from the `View` given to the LLM)."""

    summary: str | None = None
    """An optional summary of the events being forgotten."""

    summary_offset: int | None = None
    """An optional offset to the start of the resulting view indicating where the summary should be inserted."""

    source: SourceType = "environment"

    @property
    def forgotten(self) -> list[str]:
        """The list of event IDs that should be forgotten."""
        if self.forgotten_event_ids is not None:
            return self.forgotten_event_ids
        else:
            return []

    @property
    def message(self) -> str:
        if self.summary:
            return f'Summary: {self.summary}'
        return f'Condenser is dropping the events: {self.forgotten}.'


class CondensationRequest(EventBase):
    """This action is used to request a condensation of the conversation history.

    Attributes:
        action (str): The action type, namely ActionType.CONDENSATION_REQUEST.
    """

    source: SourceType = "environment"

    @property
    def message(self) -> str:
        return 'Requesting a condensation of the conversation history.'
