from dataclasses import dataclass, field
from uuid import UUID

from openhands.agent_server.models import (
    EventPage,
    TaskEvent,
)
from openhands.agent_server.pub_sub import PubSub, Subscriber
from openhands.sdk.event.llm_convertible.action import ActionEvent
from openhands.sdk.event.types import EventID
from openhands.tools.execute_bash.definition import ExecuteBashAction
from openhands.tools.execute_bash.impl import BashExecutor


@dataclass
class BashTaskService:
    """Service for executing bash tasks which are not added to the event stream and will
    not be visible to the agent. Uses an independent bash executor configured lazily
    on first use."""

    _pub_sub: PubSub = field(default_factory=PubSub, init=False)
    _bash_executor: BashExecutor | None = field(default=None, init=False)

    async def get_event(self, event_id: UUID) -> TaskEvent | None:
        """Get the event with the id given, or None if there was no such event."""
        raise NotImplementedError()

    async def batch_get_events(self, task_ids: list[UUID]) -> list[TaskEvent | None]:
        """Given a list of ids, get bash tasks (Or none for any which were not found)"""
        raise NotImplementedError()

    async def search_events(
        self,
        action_id: EventID | None = None,
        page_id: str | None = None,
        limit: int = 100,
    ) -> EventPage:
        """Search for events. If an action_id is given, only the observations for the
        action are returned."""
        raise NotImplementedError()

    async def start_bash_task(self, action: ExecuteBashAction) -> ActionEvent:
        """Given a list of ids, get bash tasks (Or none for any which were not found)"""
        raise NotImplementedError()

    async def subscribe_to_events(self, subscriber: Subscriber) -> UUID:
        """Subscribe to bash tasks. The subscriber will receive ActionEvent and
        ObservationEvent instances."""
        return self._pub_sub.subscribe(subscriber)

    async def unsubscribe_from_events(self, subscriber_id: UUID) -> bool:
        return self._pub_sub.unsubscribe(subscriber_id)

    async def __aenter__(self):
        """Start using this task service"""
        raise NotImplementedError()

    async def __aexit__(self, exc_type, exc_value, traceback):
        """Finish using this task service"""
        raise NotImplementedError()
