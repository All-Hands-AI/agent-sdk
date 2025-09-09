from openhands.sdk.event.base import EventBase
from openhands.sdk.event.types import SourceType


class Condensation(EventBase):
    """This action indicates a condensation of the conversation history is happening."""

    forgotten_event_ids: list[str]
    """The IDs of the events that are being forgotten (removed from the `View` given to
    the LLM).
    """

    summary: str | None = None
    """An optional summary of the events being forgotten."""

    summary_offset: int | None = None
    """An optional offset to the start of the resulting view indicating where the
    summary should be inserted.
    """

    source: SourceType = "environment"

    @property
    def message(self) -> str:
        if self.summary:
            return f"Summary: {self.summary}"
        return f"Condenser is dropping the events: {self.forgotten_event_ids}."


class CondensationRequest(EventBase):
    """This action is used to request a condensation of the conversation history.

    Attributes:
        action (str): The action type, namely ActionType.CONDENSATION_REQUEST.
    """

    source: SourceType = "environment"

    @property
    def message(self) -> str:
        return "Requesting a condensation of the conversation history."
