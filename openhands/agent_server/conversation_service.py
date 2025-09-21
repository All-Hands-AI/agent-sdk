import asyncio
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID, uuid4

import httpx

from openhands.agent_server.config import Config, WebhookSpec
from openhands.agent_server.event_service import EventService
from openhands.agent_server.models import (
    ConversationInfo,
    ConversationPage,
    ConversationSortOrder,
    StartConversationRequest,
    StoredConversation,
)
from openhands.agent_server.pub_sub import Subscriber
from openhands.agent_server.utils import utc_now
from openhands.sdk import EventBase, Message
from openhands.sdk.conversation.state import AgentExecutionStatus


logger = logging.getLogger(__name__)


@dataclass
class ConversationService:
    """
    Conversation service which stores to a local file store. When the context starts
    all event_services are loaded into memory, and stored when it stops.
    """

    event_services_path: Path = field(default=Path("workspace/event_services"))
    workspace_path: Path = field(default=Path("workspace/project"))
    webhook_specs: list[WebhookSpec] = field(default_factory=list)
    session_api_key: str | None = field(default=None)
    _event_services: dict[UUID, EventService] | None = field(default=None, init=False)

    async def get_conversation(self, conversation_id: UUID) -> ConversationInfo | None:
        if self._event_services is None:
            raise ValueError("inactive_service")
        event_service = self._event_services.get(conversation_id)
        if event_service is None:
            return None
        status = await event_service.get_status()
        return ConversationInfo(**event_service.stored.model_dump(), status=status)

    async def search_conversations(
        self,
        page_id: str | None = None,
        limit: int = 100,
        status: AgentExecutionStatus | None = None,
        sort_order: ConversationSortOrder = ConversationSortOrder.CREATED_AT_DESC,
    ) -> ConversationPage:
        if self._event_services is None:
            raise ValueError("inactive_service")

        # Collect all conversations with their info
        all_conversations = []
        for id, event_service in self._event_services.items():
            conversation_info = ConversationInfo(
                **event_service.stored.model_dump(),
                status=await event_service.get_status(),
            )

            # Apply status filter if provided
            if status is not None and conversation_info.status != status:
                continue

            all_conversations.append((id, conversation_info))

        # Sort conversations based on sort_order
        if sort_order == ConversationSortOrder.CREATED_AT:
            all_conversations.sort(key=lambda x: x[1].created_at)
        elif sort_order == ConversationSortOrder.CREATED_AT_DESC:
            all_conversations.sort(key=lambda x: x[1].created_at, reverse=True)
        elif sort_order == ConversationSortOrder.UPDATED_AT:
            all_conversations.sort(key=lambda x: x[1].updated_at)
        elif sort_order == ConversationSortOrder.UPDATED_AT_DESC:
            all_conversations.sort(key=lambda x: x[1].updated_at, reverse=True)

        # Handle pagination
        items = []
        start_index = 0

        # Find the starting point if page_id is provided
        if page_id:
            for i, (id, _) in enumerate(all_conversations):
                if id.hex == page_id:
                    start_index = i
                    break

        # Collect items for this page
        next_page_id = None
        for i in range(start_index, len(all_conversations)):
            if len(items) >= limit:
                # We have more items, set next_page_id
                if i < len(all_conversations):
                    next_page_id = all_conversations[i][0].hex
                break
            items.append(all_conversations[i][1])

        return ConversationPage(items=items, next_page_id=next_page_id)

    async def count_conversations(
        self,
        status: AgentExecutionStatus | None = None,
    ) -> int:
        """Count conversations matching the given filters."""
        if self._event_services is None:
            raise ValueError("inactive_service")

        count = 0
        for event_service in self._event_services.values():
            conversation_status = await event_service.get_status()

            # Apply status filter if provided
            if status is not None and conversation_status != status:
                continue

            count += 1

        return count

    async def batch_get_conversations(
        self, conversation_ids: list[UUID]
    ) -> list[ConversationInfo | None]:
        """Given a list of ids, get a batch of conversation info, returning
        None for any that were not found."""
        results = []
        for id in conversation_ids:
            result = await self.get_conversation(id)
            results.append(result)
        return results

    # Write Methods

    async def start_conversation(
        self, request: StartConversationRequest
    ) -> ConversationInfo:
        """Start a local event_service and return its id."""
        if self._event_services is None:
            raise ValueError("inactive_service")
        conversation_id = uuid4()
        stored = StoredConversation(id=conversation_id, **request.model_dump())
        file_store_path = (
            self.event_services_path / conversation_id.hex / "event_service"
        )
        file_store_path.mkdir(parents=True)
        event_service = EventService(
            stored=stored,
            file_store_path=file_store_path,
            working_dir=self.workspace_path,
        )

        # Create subscribers...
        await event_service.subscribe_to_events(_EventSubscriber(service=event_service))
        asyncio.gather(
            *[
                event_service.subscribe_to_events(
                    WebhookSubscriber(
                        service=event_service,
                        spec=webhook_spec,
                        session_api_key=self.session_api_key,
                    )
                )
                for webhook_spec in self.webhook_specs
            ]
        )

        self._event_services[conversation_id] = event_service
        await event_service.start(conversation_id=conversation_id)
        initial_message = request.initial_message
        if initial_message:
            message = Message(
                role=initial_message.role, content=initial_message.content
            )
            await event_service.send_message(message, run=initial_message.run)

        status = await event_service.get_status()
        return ConversationInfo(**event_service.stored.model_dump(), status=status)

    async def pause_conversation(self, conversation_id: UUID) -> bool:
        if self._event_services is None:
            raise ValueError("inactive_service")
        event_service = self._event_services.get(conversation_id)
        if event_service:
            await event_service.pause()
        return bool(event_service)

    async def resume_conversation(self, conversation_id: UUID) -> bool:
        if self._event_services is None:
            raise ValueError("inactive_service")
        event_service = self._event_services.get(conversation_id)
        if event_service:
            await event_service.start(conversation_id=conversation_id)
        return bool(event_service)

    async def delete_conversation(self, conversation_id: UUID) -> bool:
        if self._event_services is None:
            raise ValueError("inactive_service")
        event_service = self._event_services.pop(conversation_id, None)
        if event_service:
            await event_service.close()
            shutil.rmtree(self.event_services_path / conversation_id.hex)
            shutil.rmtree(self.workspace_path / conversation_id.hex)
            return True
        return False

    async def get_event_service(self, conversation_id: UUID) -> EventService | None:
        if self._event_services is None:
            raise ValueError("inactive_service")
        return self._event_services.get(conversation_id)

    async def __aenter__(self):
        self.event_services_path.mkdir(parents=True, exist_ok=True)
        event_services = {}
        for event_service_dir in self.event_services_path.iterdir():
            try:
                meta_file = event_service_dir / "meta.json"
                json_str = meta_file.read_text()
                id = UUID(event_service_dir.name)
                event_services[id] = EventService(
                    stored=StoredConversation.model_validate_json(json_str),
                    file_store_path=self.event_services_path / id.hex,
                    working_dir=self.workspace_path / id.hex,
                )
            except Exception:
                logger.exception(
                    f"error_loading_event_service:{event_service_dir}", stack_info=True
                )
                shutil.rmtree(event_service_dir)
        self._event_services = event_services
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        event_services = self._event_services
        if event_services is None:
            return
        self._event_services = None
        # This stops conversations and saves meta
        await asyncio.gather(
            *[
                event_service.__aexit__(exc_type, exc_value, traceback)
                for event_service in event_services.values()
            ]
        )

    @classmethod
    def get_instance(cls, config: Config) -> "ConversationService":
        return ConversationService(
            event_services_path=config.conversations_path,
            workspace_path=config.workspace_path,
            webhook_specs=config.webhooks,
            session_api_key=config.session_api_key,
        )


@dataclass
class _EventSubscriber(Subscriber):
    service: EventService

    async def __call__(self, event: EventBase):
        self.service.stored.updated_at = utc_now()


@dataclass
class WebhookSubscriber(Subscriber):
    service: EventService
    spec: WebhookSpec
    session_api_key: str | None = None
    queue: list[EventBase] = field(default_factory=list)

    async def __call__(self, event: EventBase):
        """Add event to queue and post to webhook when buffer size is reached."""
        self.queue.append(event)

        if len(self.queue) >= self.spec.event_buffer_size:
            await self._post_events()

    async def close(self):
        """Post any remaining items in the queue to the webhook."""
        if self.queue:
            await self._post_events()

    async def _post_events(self):
        """Post queued events to the webhook with retry logic."""
        if not self.queue:
            return

        events_to_post = self.queue.copy()
        self.queue.clear()

        # Prepare headers
        headers = self.spec.headers.copy()
        if self.session_api_key:
            headers["X-Session-API-Key"] = self.session_api_key

        # Convert events to serializable format
        event_data = [
            event.model_dump() if hasattr(event, "model_dump") else event.__dict__
            for event in events_to_post
        ]

        # Retry logic
        for attempt in range(self.spec.num_retries + 1):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.request(
                        method=self.spec.method,
                        url=self.spec.webhook_url,
                        json=event_data,
                        headers=headers,
                        timeout=30.0,
                    )
                    response.raise_for_status()
                    logger.debug(
                        f"Successfully posted {len(event_data)} events "
                        f"to webhook {self.spec.webhook_url}"
                    )
                    return
            except Exception as e:
                logger.warning(f"Webhook post attempt {attempt + 1} failed: {e}")
                if attempt < self.spec.num_retries:
                    await asyncio.sleep(self.spec.retry_delay)
                else:
                    logger.error(
                        f"Failed to post events to webhook {self.spec.webhook_url} "
                        f"after {self.spec.num_retries + 1} attempts"
                    )
                    # Re-queue events for potential retry later
                    self.queue.extend(events_to_post)


_conversation_service: ConversationService | None = None


def get_default_conversation_service() -> ConversationService:
    global _conversation_service
    if _conversation_service:
        return _conversation_service

    from openhands.agent_server.config import (
        get_default_config,
    )

    config = get_default_config()
    _conversation_service = ConversationService.get_instance(config)
    return _conversation_service
