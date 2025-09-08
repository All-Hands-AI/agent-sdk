from openhands.sdk.event.base import EventBase
from openhands.sdk.event.types import SourceType


class PauseEvent(EventBase):
    """Event indicating that the agent execution was paused by user request."""

    source: SourceType = "user"

    def __str__(self) -> str:
        """Plain text string representation for PauseEvent."""
        return f"{self.__class__.__name__} ({self.source}): Agent execution paused"
