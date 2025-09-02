from openhands.core.event.base import EventBase


class Condensation(EventBase):
    """This action indicates a condensation of the conversation history is happening.

    There are two ways to specify the events to be forgotten:
    1. By providing a list of event IDs.
    2. By providing the start and end IDs of a range of events.

    In the second case, we assume that event IDs are monotonically increasing, and that _all_ events between the start and end IDs are to be forgotten.

    Raises:
        ValueError: If the optional fields are not instantiated in a valid configuration.
    """
    
    forgotten_event_ids: list[int] | None = None
    """The IDs of the events that are being forgotten (removed from the `View` given to the LLM)."""

    forgotten_events_start_id: int | None = None
    """The ID of the first event to be forgotten in a range of events."""

    forgotten_events_end_id: int | None = None
    """The ID of the last event to be forgotten in a range of events."""

    summary: str | None = None
    """An optional summary of the events being forgotten."""

    summary_offset: int | None = None
    """An optional offset to the start of the resulting view indicating where the summary should be inserted."""

    def _validate_field_polymorphism(self) -> bool:
        """Check if the optional fields are instantiated in a valid configuration."""
        # For the forgotton events, there are only two valid configurations:
        # 1. We're forgetting events based on the list of provided IDs, or
        using_event_ids = self.forgotten_event_ids is not None
        # 2. We're forgetting events based on the range of IDs.
        using_event_range = (
            self.forgotten_events_start_id is not None
            and self.forgotten_events_end_id is not None
        )

        # Either way, we can only have one of the two valid configurations.
        forgotten_event_configuration = using_event_ids ^ using_event_range

        # We also need to check that if the summary is provided, so is the
        # offset (and vice versa).
        summary_configuration = (
            self.summary is None and self.summary_offset is None
        ) or (self.summary is not None and self.summary_offset is not None)

        return forgotten_event_configuration and summary_configuration

    def __post_init__(self):
        if not self._validate_field_polymorphism():
            raise ValueError('Invalid configuration of the optional fields.')

    @property
    def forgotten(self) -> list[int]:
        """The list of event IDs that should be forgotten."""
        # Start by making sure the fields are instantiated in a valid
        # configuration. We check this whenever the event is initialized, but we
        # can't make the dataclass immutable so we need to check it again here
        # to make sure the configuration is still valid.
        if not self._validate_field_polymorphism():
            raise ValueError('Invalid configuration of the optional fields.')

        if self.forgotten_event_ids is not None:
            return self.forgotten_event_ids

        # If we've gotten this far, the start/end IDs are not None.
        assert self.forgotten_events_start_id is not None
        assert self.forgotten_events_end_id is not None
        return list(
            range(self.forgotten_events_start_id, self.forgotten_events_end_id + 1)
        )

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

    @property
    def message(self) -> str:
        return 'Requesting a condensation of the conversation history.'
