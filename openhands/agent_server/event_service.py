import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

from openhands.agent_server.models import (
    ConfirmationResponseRequest,
    EventPage,
    EventSortOrder,
    EventType,
    StoredConversation,
)
from openhands.agent_server.pub_sub import PubSub, Subscriber
from openhands.agent_server.utils import utc_now
from openhands.sdk import (
    Agent,
    Conversation,
    LocalFileStore,
    Message,
)
from openhands.sdk.conversation.state import AgentExecutionStatus
from openhands.sdk.utils.async_utils import AsyncCallbackWrapper


@dataclass
class EventService:
    """
    Event service for a conversation running locally, analogous to a conversation
    in the SDK. Async mostly for forward compatibility
    """

    stored: StoredConversation
    file_store_path: Path
    working_dir: Path
    _conversation: Conversation | None = field(default=None, init=False)
    _pub_sub: PubSub = field(default_factory=PubSub, init=False)

    async def load_meta(self):
        meta_file = self.file_store_path / "meta.json"
        self.stored = StoredConversation.model_validate_json(meta_file.read_text())

    async def save_meta(self):
        self.stored.updated_at = utc_now()
        meta_file = self.file_store_path / "meta.json"
        meta_file.write_text(self.stored.model_dump_json())

    async def get_event(self, event_id: str) -> EventType | None:
        if not self._conversation:
            raise ValueError("inactive_service")
        with self._conversation.state as state:
            # TODO: It would be nice if the agent sdk had a method for
            #       getting events by id
            event = next(
                (event for event in state.events if event.id == event_id), None
            )
            return event

    async def search_events(
        self,
        page_id: str | None = None,
        limit: int = 100,
        kind: str | None = None,
        sort_order: EventSortOrder = EventSortOrder.TIMESTAMP,
    ) -> EventPage:
        if not self._conversation:
            raise ValueError("inactive_service")

        # Collect all events
        all_events = []
        with self._conversation.state as state:
            for event in state.events:
                # Apply kind filter if provided
                if (
                    kind is not None
                    and f"{event.__class__.__module__}.{event.__class__.__name__}"
                    != kind
                ):
                    continue
                all_events.append(event)

        # Sort events based on sort_order
        if sort_order == EventSortOrder.TIMESTAMP:
            all_events.sort(key=lambda x: x.timestamp)
        elif sort_order == EventSortOrder.TIMESTAMP_DESC:
            all_events.sort(key=lambda x: x.timestamp, reverse=True)

        # Handle pagination
        items = []
        start_index = 0

        # Find the starting point if page_id is provided
        if page_id:
            for i, event in enumerate(all_events):
                if event.id == page_id:
                    start_index = i
                    break

        # Collect items for this page
        next_page_id = None
        for i in range(start_index, len(all_events)):
            if len(items) >= limit:
                # We have more items, set next_page_id
                if i < len(all_events):
                    next_page_id = all_events[i].id
                break
            items.append(all_events[i])

        if items:
            from pydantic import TypeAdapter

            ta = TypeAdapter(EventType)
            ta.dump_json(items[0])
        return EventPage(items=items, next_page_id=next_page_id)

    async def count_events(
        self,
        kind: str | None = None,
    ) -> int:
        """Count events matching the given filters."""
        if not self._conversation:
            raise ValueError("inactive_service")

        count = 0
        with self._conversation.state as state:
            for event in state.events:
                # Apply kind filter if provided
                if (
                    kind is not None
                    and f"{event.__class__.__module__}.{event.__class__.__name__}"
                    != kind
                ):
                    continue
                count += 1

        return count

    async def batch_get_events(self, event_ids: list[str]) -> list[EventType | None]:
        """Given a list of ids, get events (Or none for any which were not found)"""
        results = []
        for event_id in event_ids:
            result = await self.get_event(event_id)
            results.append(result)
        return results

    async def send_message(self, message: Message, run: bool = True):
        if not self._conversation:
            raise ValueError("inactive_service")
        loop = asyncio.get_running_loop()
        future = loop.run_in_executor(None, self._conversation.send_message, message)
        if run:
            await future
            loop.run_in_executor(None, self._conversation.run)

    async def subscribe_to_events(self, subscriber: Subscriber) -> UUID:
        return self._pub_sub.subscribe(subscriber)

    async def unsubscribe_from_events(self, subscriber_id: UUID) -> bool:
        return self._pub_sub.unsubscribe(subscriber_id)

    async def start(self, conversation_id: UUID):
        # self.stored is a subclass of AgentSpec so we can create an agent from it
        self.file_store_path.mkdir(parents=True, exist_ok=True)
        self.working_dir.mkdir(parents=True, exist_ok=True)
        loop = asyncio.get_running_loop()
        agent = await loop.run_in_executor(None, Agent.from_spec, self.stored)
        conversation = Conversation(
            agent=agent,
            persist_filestore=LocalFileStore(
                str(self.file_store_path)
                # inside Conversation, events will be saved to
                # "file_store_path/{convo_id}/events"
            ),
            conversation_id=conversation_id,
            callbacks=[
                AsyncCallbackWrapper(self._pub_sub, loop=asyncio.get_running_loop())
            ],
            max_iteration_per_run=self.stored.max_iterations,
            visualize=False,
        )

        # Set confirmation mode if enabled
        conversation.set_confirmation_mode(self.stored.confirmation_mode)
        self._conversation = conversation

    async def run(self):
        """Run the conversation asynchronously."""
        if not self._conversation:
            raise ValueError("inactive_service")
        loop = asyncio.get_running_loop()
        loop.run_in_executor(None, self._conversation.run)

    async def respond_to_confirmation(self, request: ConfirmationResponseRequest):
        if request.accept:
            await self.run()
        else:
            await self.pause()

    async def pause(self):
        if self._conversation:
            loop = asyncio.get_running_loop()
            loop.run_in_executor(None, self._conversation.pause)

    async def close(self):
        await self._pub_sub.close()
        if self._conversation:
            loop = asyncio.get_running_loop()
            loop.run_in_executor(None, self._conversation.close)

    async def get_status(self) -> AgentExecutionStatus:
        if not self._conversation:
            return AgentExecutionStatus.ERROR
        return self._conversation.state.agent_status

    async def __aenter__(self, conversation_id: UUID):
        await self.start(conversation_id=conversation_id)
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.save_meta()
        await self.close()
