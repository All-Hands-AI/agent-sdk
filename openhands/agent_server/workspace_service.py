"""
Workspace service for managing bash executor and events.
"""

import asyncio
import json
import threading
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import httpx

from openhands.agent_server.config import WebhookSpec, get_default_config
from openhands.agent_server.pub_sub import PubSub, Subscriber
from openhands.sdk.event.base import EventBase
from openhands.sdk.logger import get_logger
from openhands.tools.execute_bash import (
    BashExecutor,
    ExecuteBashAction,
    ExecuteBashObservation,
)


logger = get_logger(__name__)


@dataclass
class BashWebhookSubscriber(Subscriber):
    """Webhook subscriber for bash events."""

    spec: WebhookSpec
    session_api_key: str | None = None
    queue: list[EventBase] = field(default_factory=list)
    _flush_timer: asyncio.Task | None = field(default=None, init=False)

    async def __call__(self, event: EventBase):
        """Add bash event to queue and post to webhook when buffer size is reached."""
        self.queue.append(event)

        if len(self.queue) >= self.spec.event_buffer_size:
            # Cancel timer since we're flushing due to buffer size
            self._cancel_flush_timer()
            await self._post_events()
        else:
            # Reset the flush timer
            self._reset_flush_timer()

    async def close(self):
        """Post any remaining items in the queue to the webhook."""
        # Cancel any pending flush timer
        self._cancel_flush_timer()

        if self.queue:
            await self._post_events()

    async def _post_events(self):
        """Post queued bash events to the webhook with retry logic."""
        if not self.queue:
            return

        events_to_post = self.queue.copy()
        self.queue.clear()

        # Prepare headers
        headers = self.spec.headers.copy()
        if self.session_api_key:
            headers["X-Session-API-Key"] = self.session_api_key

        # Convert events to serializable format
        event_data = []
        for event in events_to_post:
            if isinstance(event, BashEvent):
                event_data.append(event.to_dict())
            else:
                event_data.append(event.model_dump())

        # Construct bash events URL
        bash_events_url = f"{self.spec.base_url.rstrip('/')}/bash-events"

        # Retry logic
        for attempt in range(self.spec.num_retries + 1):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.request(
                        method="POST",
                        url=bash_events_url,
                        json=event_data,
                        headers=headers,
                        timeout=30.0,
                    )
                    response.raise_for_status()
                    logger.debug(
                        f"Successfully posted {len(event_data)} bash events "
                        f"to webhook {bash_events_url}"
                    )
                    return
            except Exception as e:
                logger.warning(f"Bash webhook post attempt {attempt + 1} failed: {e}")
                if attempt < self.spec.num_retries:
                    await asyncio.sleep(self.spec.retry_delay)
                else:
                    logger.error(
                        f"Failed to post bash events to webhook {bash_events_url} "
                        f"after {self.spec.num_retries + 1} attempts"
                    )
                    # Re-queue events for potential retry later
                    self.queue.extend(events_to_post)

    def _cancel_flush_timer(self):
        """Cancel the current flush timer if it exists."""
        if self._flush_timer and not self._flush_timer.done():
            self._flush_timer.cancel()
            self._flush_timer = None

    def _reset_flush_timer(self):
        """Reset the flush timer to trigger after the specified delay."""
        self._cancel_flush_timer()

        async def _flush_after_delay():
            await asyncio.sleep(self.spec.flush_delay)
            await self._post_events()

        self._flush_timer = asyncio.create_task(_flush_after_delay())


class BashEvent(EventBase):
    """Represents a bash command execution event."""

    action: ExecuteBashAction
    observation: ExecuteBashObservation | None = None

    def __init__(
        self,
        action: ExecuteBashAction,
        observation: ExecuteBashObservation | None = None,
        **kwargs,
    ):
        # Set the action and observation as instance attributes
        object.__setattr__(self, "action", action)
        object.__setattr__(self, "observation", observation)
        super().__init__(source="agent", **kwargs)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "source": self.source,
            "action": self.action.model_dump(),
            "observation": self.observation.model_dump() if self.observation else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BashEvent":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            timestamp=data["timestamp"],
            action=ExecuteBashAction.model_validate(data["action"]),
            observation=(
                ExecuteBashObservation.model_validate(data["observation"])
                if data["observation"]
                else None
            ),
        )


class WorkspaceService:
    """Service for managing workspace operations including bash execution and file operations."""  # noqa: E501

    def __init__(self, config=None):
        self.config = config or get_default_config()
        self._bash_executor: BashExecutor | None = None
        self._executor_lock = threading.Lock()
        self._events: list[BashEvent] = []
        self._events_lock = threading.Lock()
        self._pub_sub = PubSub()
        self._webhook_subscribers: list[BashWebhookSubscriber] = []
        self._load_events()
        self._initialize_webhook_subscribers()

    def _get_bash_executor(self) -> BashExecutor:
        """Get or create bash executor (lazy initialization)."""
        if self._bash_executor is None:
            with self._executor_lock:
                if self._bash_executor is None:
                    self._bash_executor = BashExecutor(
                        working_dir=str(self.config.workspace_path)
                    )
        return self._bash_executor

    def _load_events(self) -> None:
        """Load events from the events file."""
        try:
            if self.config.bash_events_path.exists():
                with open(self.config.bash_events_path, "r") as f:
                    data = json.load(f)
                    self._events = [
                        BashEvent.from_dict(event_data) for event_data in data
                    ]
                logger.info(
                    f"Loaded {len(self._events)} bash events from "
                    f"{self.config.bash_events_path}"
                )
        except Exception as e:
            logger.error(f"Failed to load bash events: {e}")
            self._events = []

    def _save_events(self) -> None:
        """Save events to the events file."""
        try:
            # Ensure the directory exists
            self.config.bash_events_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.config.bash_events_path, "w") as f:
                json.dump([event.to_dict() for event in self._events], f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save bash events: {e}")

    def _initialize_webhook_subscribers(self) -> None:
        """Initialize webhook subscribers for bash events."""
        for webhook_spec in self.config.webhooks:
            subscriber = BashWebhookSubscriber(
                spec=webhook_spec,
                session_api_key=self.config.session_api_key,
            )
            self._webhook_subscribers.append(subscriber)
            # Subscribe to the pub/sub system
            self._pub_sub.subscribe(subscriber)

    async def execute_bash_command(
        self, action: ExecuteBashAction
    ) -> ExecuteBashObservation:
        """Execute a bash command and store the event."""
        event = BashEvent(action=action)

        # Store the event with action only first
        with self._events_lock:
            self._events.append(event)
            self._save_events()

        # Execute the command in a background thread
        def _execute():
            executor = self._get_bash_executor()
            return executor(action)

        loop = asyncio.get_event_loop()
        observation = await loop.run_in_executor(None, _execute)

        # Create a new event with the observation (EventBase is frozen)
        completed_event = BashEvent(
            action=action,
            observation=observation,
            id=event.id,
            timestamp=event.timestamp,
        )

        with self._events_lock:
            # Replace the original event with the completed one
            for i, stored_event in enumerate(self._events):
                if stored_event.id == event.id:
                    self._events[i] = completed_event
                    break
            self._save_events()

        # Notify subscribers
        await self._pub_sub(completed_event)

        return observation

    def search_events(
        self,
        limit: int = 100,
        offset: int = 0,
        command_filter: str | None = None,
    ) -> list[BashEvent]:
        """Search bash events with optional filtering."""
        with self._events_lock:
            events = self._events.copy()

        # Apply command filter if provided
        if command_filter:
            events = [
                event
                for event in events
                if command_filter.lower() in event.action.command.lower()
            ]

        # Sort by timestamp (newest first)
        events.sort(key=lambda e: e.timestamp, reverse=True)

        # Apply pagination
        return events[offset : offset + limit]

    def get_event(self, event_id: str) -> BashEvent | None:
        """Get a specific bash event by ID."""
        with self._events_lock:
            for event in self._events:
                if event.id == event_id:
                    return event
        return None

    def count_events(self, command_filter: str | None = None) -> int:
        """Count bash events with optional filtering."""
        with self._events_lock:
            events = self._events.copy()

        if command_filter:
            events = [
                event
                for event in events
                if command_filter.lower() in event.action.command.lower()
            ]

        return len(events)

    async def subscribe_to_events(self, subscriber: Subscriber) -> UUID:
        """Subscribe to bash events."""
        return self._pub_sub.subscribe(subscriber)

    async def unsubscribe_from_events(self, subscriber_id: UUID) -> bool:
        """Unsubscribe from bash events."""
        return self._pub_sub.unsubscribe(subscriber_id)

    async def close(self):
        """Clean up the service."""
        # Close webhook subscribers first to flush any pending events
        for subscriber in self._webhook_subscribers:
            await subscriber.close()
        self._webhook_subscribers.clear()

        await self._pub_sub.close()
        if self._bash_executor:
            # Close the bash executor if it has a close method
            if hasattr(self._bash_executor, "close"):
                self._bash_executor.close()


# Global service instance
_default_workspace_service: WorkspaceService | None = None


def get_default_workspace_service() -> WorkspaceService:
    """Get the default workspace service shared across the server."""
    global _default_workspace_service
    if _default_workspace_service is None:
        _default_workspace_service = WorkspaceService()
    return _default_workspace_service
