import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

from openhands.agent_server.models import (
    ConfirmationResponseRequest,
    EventPage,
    EventSortOrder,
    StoredConversation,
)
from openhands.agent_server.pub_sub import PubSub, Subscriber
from openhands.agent_server.utils import utc_now
from openhands.sdk import Agent, EventBase, LocalFileStore, Message, get_logger
from openhands.sdk.conversation.impl.local_conversation import LocalConversation
from openhands.sdk.conversation.secrets_manager import SecretValue
from openhands.sdk.conversation.state import ConversationState
from openhands.sdk.security.confirmation_policy import ConfirmationPolicyBase
from openhands.sdk.utils.async_utils import AsyncCallbackWrapper


logger = get_logger(__name__)


@dataclass
class EventService:
    """
    Event service for a conversation running locally, analogous to a conversation
    in the SDK. Async mostly for forward compatibility
    """

    stored: StoredConversation
    file_store_path: Path
    working_dir: Path
    _conversation: LocalConversation | None = field(default=None, init=False)
    _pub_sub: PubSub[EventBase] = field(
        default_factory=lambda: PubSub[EventBase](), init=False
    )
    _run_task: asyncio.Task | None = field(default=None, init=False)

    async def load_meta(self):
        meta_file = self.file_store_path / "meta.json"
        self.stored = StoredConversation.model_validate_json(meta_file.read_text())

    async def save_meta(self):
        self.stored.updated_at = utc_now()
        meta_file = self.file_store_path / "meta.json"
        meta_file.write_text(self.stored.model_dump_json())

    async def get_event(self, event_id: str) -> EventBase | None:
        if not self._conversation:
            raise ValueError("inactive_service")
        with self._conversation._state as state:
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
        with self._conversation._state as state:
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

        return EventPage(items=items, next_page_id=next_page_id)

    async def count_events(
        self,
        kind: str | None = None,
    ) -> int:
        """Count events matching the given filters."""
        if not self._conversation:
            raise ValueError("inactive_service")

        count = 0
        with self._conversation._state as state:
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

    async def batch_get_events(self, event_ids: list[str]) -> list[EventBase | None]:
        """Given a list of ids, get events (Or none for any which were not found)"""
        results = []
        for event_id in event_ids:
            result = await self.get_event(event_id)
            results.append(result)
        return results

    async def send_message(self, message: Message):
        if not self._conversation:
            raise ValueError("inactive_service")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._conversation.send_message, message)

    async def subscribe_to_events(self, subscriber: Subscriber[EventBase]) -> UUID:
        return self._pub_sub.subscribe(subscriber)

    async def unsubscribe_from_events(self, subscriber_id: UUID) -> bool:
        return self._pub_sub.unsubscribe(subscriber_id)

    async def start(self):
        # self.stored contains an Agent configuration we can instantiate
        self.file_store_path.mkdir(parents=True, exist_ok=True)
        self.working_dir.mkdir(parents=True, exist_ok=True)
        agent = Agent.model_validate(self.stored.agent.model_dump())
        conversation = LocalConversation(
            agent=agent,
            persist_filestore=LocalFileStore(
                str(self.file_store_path)
                # inside Conversation, events will be saved to
                # "file_store_path/{convo_id}/events"
            ),
            conversation_id=self.stored.id,
            callbacks=[
                AsyncCallbackWrapper(self._pub_sub, loop=asyncio.get_running_loop())
            ],
            max_iteration_per_run=self.stored.max_iterations,
            stuck_detection=self.stored.stuck_detection,
            visualize=False,
        )

        # Set confirmation mode if enabled
        conversation.set_confirmation_policy(self.stored.confirmation_policy)
        self._conversation = conversation

    async def run(self):
        """Run the conversation asynchronously."""
        if not self._conversation:
            raise ValueError("inactive_service")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._conversation.run)

    async def respond_to_confirmation(self, request: ConfirmationResponseRequest):
        if request.accept:
            await self.run()
        else:
            await self.pause()

    async def pause(self):
        if self._conversation:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._conversation.pause)

    async def update_secrets(self, secrets: dict[str, SecretValue]):
        """Update secrets in the conversation."""
        if not self._conversation:
            raise ValueError("inactive_service")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._conversation.update_secrets, secrets)

    async def set_confirmation_policy(self, policy: ConfirmationPolicyBase):
        """Set the confirmation policy for the conversation."""
        if not self._conversation:
            raise ValueError("inactive_service")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None, self._conversation.set_confirmation_policy, policy
        )

    async def close(self):
        await self._pub_sub.close()
        if self._conversation:
            loop = asyncio.get_running_loop()
            loop.run_in_executor(None, self._conversation.close)

    async def get_state(self) -> ConversationState:
        if not self._conversation:
            raise ValueError("inactive_service")
        return self._conversation._state

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.save_meta()
        await self.close()
