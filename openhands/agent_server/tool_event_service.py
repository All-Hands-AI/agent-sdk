import asyncio
import glob
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

from openhands.agent_server.models import (
    ToolEvent,
    ToolEventPage,
)
from openhands.agent_server.pub_sub import PubSub, Subscriber
from openhands.sdk.event.llm_convertible.action import ActionEvent
from openhands.sdk.event.llm_convertible.observation import ObservationEvent
from openhands.sdk.event.types import EventID
from openhands.sdk.logger import get_logger
from openhands.tools.execute_bash.definition import ExecuteBashAction
from openhands.tools.execute_bash.impl import BashExecutor


logger = get_logger(__name__)


@dataclass
class ToolEventService:
    """Service for executing tool events which are not added to the event stream and
    will not be visible to the agent. Uses an independent bash executor configured
    lazily on first use."""

    working_dir: Path = field()
    tool_events_dir: Path = field()
    _pub_sub: PubSub = field(default_factory=PubSub, init=False)
    _bash_executor: BashExecutor | None = field(default=None, init=False)
    _action_to_observation: dict[str, str] = field(default_factory=dict, init=False)

    def _ensure_bash_executor(self) -> BashExecutor:
        """Lazily initialize the bash executor if not already created."""
        if self._bash_executor is None:
            self._bash_executor = BashExecutor(working_dir=str(self.working_dir))
            logger.info(
                f"ToolEventService initialized executor with working_dir: "
                f"{self.working_dir}"
            )
        return self._bash_executor

    def _ensure_tool_events_dir(self) -> None:
        """Ensure the tool events directory exists."""
        self.tool_events_dir.mkdir(parents=True, exist_ok=True)

    def _get_event_filename(self, event: ToolEvent) -> str:
        """Generate filename using YYYYMMDDHHMMSS_eventId_actionId format."""
        # Parse ISO timestamp string to datetime object
        timestamp_dt = datetime.fromisoformat(event.timestamp.replace("Z", "+00:00"))
        timestamp = timestamp_dt.strftime("%Y%m%d%H%M%S")
        action_id = getattr(event, "action_id", "none")
        return f"{timestamp}_{event.id}_{action_id}"

    def _save_event_to_file(self, event: ToolEvent) -> None:
        """Save an event to a file."""
        self._ensure_tool_events_dir()
        filename = self._get_event_filename(event)
        filepath = self.tool_events_dir / filename

        # Convert event to dict for JSON serialization
        event_data = {"type": event.__class__.__name__, "data": event.model_dump()}

        with open(filepath, "w") as f:
            json.dump(event_data, f, indent=2)

    def _load_event_from_file(self, filepath: Path) -> ToolEvent | None:
        """Load an event from a file."""
        try:
            with open(filepath, "r") as f:
                event_data = json.load(f)

            # Import the event classes
            from openhands.sdk.event.llm_convertible.action import ActionEvent
            from openhands.sdk.event.llm_convertible.observation import ObservationEvent

            # Reconstruct the event based on type
            event_type = event_data["type"]
            if event_type == "ActionEvent":
                return ActionEvent(**event_data["data"])
            elif event_type == "ObservationEvent":
                return ObservationEvent(**event_data["data"])
            else:
                logger.warning(f"Unknown event type: {event_type}")
                return None
        except Exception as e:
            logger.error(f"Error loading event from {filepath}: {e}")
            return None

    def _get_event_files_by_pattern(self, pattern: str) -> list[Path]:
        """Get event files matching a glob pattern, sorted by timestamp."""
        self._ensure_tool_events_dir()
        files = glob.glob(str(self.tool_events_dir / pattern))
        return sorted([Path(f) for f in files])

    async def get_event(self, event_id: str) -> ToolEvent | None:
        """Get the event with the id given, or None if there was no such event."""
        # Use glob pattern to find files with the event_id
        pattern = f"*_{event_id}_*"
        files = self._get_event_files_by_pattern(pattern)

        if not files:
            return None

        # Load and return the first matching event
        return self._load_event_from_file(files[0])

    async def batch_get_events(self, task_ids: list[str]) -> list[ToolEvent | None]:
        """Given a list of ids, get tool events (Or none for any which were
        not found)"""
        results = []
        for task_id in task_ids:
            result = await self.get_event(task_id)
            results.append(result)
        return results

    async def search_events(
        self,
        action_id: EventID | None = None,
        page_id: str | None = None,
        limit: int = 100,
    ) -> ToolEventPage:
        """Search for events. If an action_id is given, only the observations for the
        action are returned."""
        # Get files based on action_id filter
        if action_id is not None:
            # Use glob pattern to filter by action_id
            pattern = f"*_{action_id}"
            files = self._get_event_files_by_pattern(pattern)
        else:
            # Get all event files
            pattern = "*"
            files = self._get_event_files_by_pattern(pattern)

        # Load all events from files
        all_events = []
        for file_path in files:
            event = self._load_event_from_file(file_path)
            if event is not None:
                all_events.append(event)

        # Additional filtering for action_id if needed (for both action and
        # observation events)
        if action_id is not None:
            filtered_events = []
            for event in all_events:
                if isinstance(event, ActionEvent) and str(event.id) == action_id:
                    filtered_events.append(event)
                elif (
                    isinstance(event, ObservationEvent) and event.action_id == action_id
                ):
                    filtered_events.append(event)
            all_events = filtered_events

        # Sort events by timestamp (files are already sorted by timestamp in filename)
        all_events.sort(key=lambda x: x.timestamp)

        # Handle pagination
        items = []
        start_index = 0

        # Find the starting point if page_id is provided
        if page_id:
            for i, event in enumerate(all_events):
                if str(event.id) == page_id:
                    start_index = i
                    break

        # Collect items for this page
        next_page_id = None
        for i in range(start_index, len(all_events)):
            if len(items) >= limit:
                # We have more items, set next_page_id
                if i < len(all_events):
                    next_page_id = str(all_events[i].id)
                break
            items.append(all_events[i])

        return ToolEventPage(items=items, next_page_id=next_page_id)

    async def start_bash_execution(self, action: ExecuteBashAction) -> ActionEvent:
        """Execute a tool event and return the action event.
        The observation will be published separately."""
        # Create action event
        action_id = str(uuid4())
        tool_call_id = str(uuid4())
        llm_response_id = str(uuid4())

        # Create a minimal tool call for the action event
        from litellm import ChatCompletionMessageToolCall

        tool_call = ChatCompletionMessageToolCall(
            id=tool_call_id,
            function={
                "name": "execute_bash",
                "arguments": action.model_dump_json(),
            },
            type="function",
        )

        action_event = ActionEvent(
            id=action_id,
            thought=[],  # Empty thought for tool events
            action=action,
            tool_name="execute_bash",
            tool_call_id=tool_call_id,
            tool_call=tool_call,
            llm_response_id=llm_response_id,
        )

        # Store the action event to file
        self._save_event_to_file(action_event)

        # Publish the action event
        await self._pub_sub(action_event)

        # Execute the bash command in a background task
        asyncio.create_task(self._execute_tool_event(action_event))

        return action_event

    async def _execute_tool_event(self, action_event: ActionEvent) -> None:
        """Execute the tool event and create an observation event."""
        try:
            # Get the bash executor
            executor = self._ensure_bash_executor()

            # Execute the command - cast to ExecuteBashAction for type safety
            bash_action = action_event.action
            assert isinstance(bash_action, ExecuteBashAction)
            loop = asyncio.get_running_loop()
            observation = await loop.run_in_executor(None, executor, bash_action)

            # Create observation event
            observation_id = str(uuid4())
            observation_event = ObservationEvent(
                id=observation_id,
                action_id=action_event.id,
                observation=observation,
                tool_name="execute_bash",
                tool_call_id=action_event.tool_call_id,
            )

            # Store the observation event to file and link it to the action
            self._save_event_to_file(observation_event)
            self._action_to_observation[action_event.id] = observation_id

            # Publish the observation event
            await self._pub_sub(observation_event)

        except Exception as e:
            logger.exception(f"Error executing tool event {action_event.id}: {e}")
            # Create an error observation
            from openhands.tools.execute_bash.definition import ExecuteBashObservation

            error_observation = ExecuteBashObservation(
                output=f"Error executing command: {str(e)}",
                error=True,
            )

            observation_id = str(uuid4())
            observation_event = ObservationEvent(
                id=observation_id,
                action_id=action_event.id,
                observation=error_observation,
                tool_name="execute_bash",
                tool_call_id=action_event.tool_call_id,
            )

            # Store and publish the error observation
            self._save_event_to_file(observation_event)
            self._action_to_observation[action_event.id] = observation_id
            await self._pub_sub(observation_event)

    async def subscribe_to_events(self, subscriber: Subscriber) -> UUID:
        """Subscribe to tool events. The subscriber will receive ActionEvent and
        ObservationEvent instances."""
        return self._pub_sub.subscribe(subscriber)

    async def unsubscribe_from_events(self, subscriber_id: UUID) -> bool:
        return self._pub_sub.unsubscribe(subscriber_id)

    async def close(self):
        """Close the tool event service and clean up resources."""
        await self._pub_sub.close()
        if self._bash_executor:
            self._bash_executor.close()

    async def __aenter__(self):
        """Start using this task service"""
        # No special initialization needed for tool event service
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        """Finish using this task service"""
        await self.close()


_tool_event_service: ToolEventService | None = None


def get_default_tool_event_service() -> ToolEventService:
    """Get the default tool event service instance."""
    global _tool_event_service
    if _tool_event_service:
        return _tool_event_service

    from openhands.agent_server.config import get_default_config

    config = get_default_config()
    _tool_event_service = ToolEventService(
        working_dir=config.workspace_path, tool_events_dir=config.tool_events_dir
    )
    return _tool_event_service
