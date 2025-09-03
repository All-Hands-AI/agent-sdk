from openhands.sdk.event.base import EventBase
from openhands.sdk.event.types import SourceType


class Condensation(EventBase):
    """This action indicates a condensation of the conversation history is happening."""

    forgotten_event_ids: list[str] | None = None
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
    def forgotten(self) -> list[str]:
        """The list of event IDs that should be forgotten."""
        if self.forgotten_event_ids is not None:
            return self.forgotten_event_ids
        else:
            return []

    @property
    def message(self) -> str:
        if self.summary:
            return f"Summary: {self.summary}"
        return f"Condenser is dropping the events: {self.forgotten}."


class CondensationRequest(EventBase):
    """This action is used to request a condensation of the conversation history.

    Attributes:
        action (str): The action type, namely ActionType.CONDENSATION_REQUEST.
    """

    source: SourceType = "environment"

    @property
    def message(self) -> str:
        return "Requesting a condensation of the conversation history."
