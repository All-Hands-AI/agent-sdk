import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID, uuid4

from openhands.agent_server.models import (
    TaskEvent,
    TaskEventPage,
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
class BashTaskService:
    """Service for executing bash tasks which are not added to the event stream and will
    not be visible to the agent. Uses an independent bash executor configured lazily
    on first use."""

    working_dir: Path = field()
    _pub_sub: PubSub = field(default_factory=PubSub, init=False)
    _bash_executor: BashExecutor | None = field(default=None, init=False)
    _task_events: dict[str, TaskEvent] = field(default_factory=dict, init=False)
    _action_to_observation: dict[str, str] = field(default_factory=dict, init=False)

    def _ensure_bash_executor(self) -> BashExecutor:
        """Lazily initialize the bash executor if not already created."""
        if self._bash_executor is None:
            self._bash_executor = BashExecutor(working_dir=str(self.working_dir))
            logger.info(
                f"BashTaskService initialized executor with working_dir: "
                f"{self.working_dir}"
            )
        return self._bash_executor

    async def get_event(self, event_id: str) -> TaskEvent | None:
        """Get the event with the id given, or None if there was no such event."""
        return self._task_events.get(event_id)

    async def batch_get_events(self, task_ids: list[str]) -> list[TaskEvent | None]:
        """Given a list of ids, get bash tasks (Or none for any which were not found)"""
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
    ) -> TaskEventPage:
        """Search for events. If an action_id is given, only the observations for the
        action are returned."""
        # Collect all events
        all_events = list(self._task_events.values())

        # Filter by action_id if provided
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

        # Sort events by timestamp
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

        return TaskEventPage(items=items, next_page_id=next_page_id)

    async def start_bash_task(self, action: ExecuteBashAction) -> ActionEvent:
        """Execute a bash task and return the action event.
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
            thought=[],  # Empty thought for bash tasks
            action=action,
            tool_name="execute_bash",
            tool_call_id=tool_call_id,
            tool_call=tool_call,
            llm_response_id=llm_response_id,
        )

        # Store the action event
        self._task_events[action_id] = action_event

        # Publish the action event
        await self._pub_sub(action_event)

        # Execute the bash command in a background task
        asyncio.create_task(self._execute_bash_task(action_event))

        return action_event

    async def _execute_bash_task(self, action_event: ActionEvent) -> None:
        """Execute the bash task and create an observation event."""
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

            # Store the observation event and link it to the action
            self._task_events[observation_id] = observation_event
            self._action_to_observation[action_event.id] = observation_id

            # Publish the observation event
            await self._pub_sub(observation_event)

        except Exception as e:
            logger.exception(f"Error executing bash task {action_event.id}: {e}")
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
            self._task_events[observation_id] = observation_event
            self._action_to_observation[action_event.id] = observation_id
            await self._pub_sub(observation_event)

    async def subscribe_to_events(self, subscriber: Subscriber) -> UUID:
        """Subscribe to bash tasks. The subscriber will receive ActionEvent and
        ObservationEvent instances."""
        return self._pub_sub.subscribe(subscriber)

    async def unsubscribe_from_events(self, subscriber_id: UUID) -> bool:
        return self._pub_sub.unsubscribe(subscriber_id)

    async def close(self):
        """Close the bash task service and clean up resources."""
        await self._pub_sub.close()
        if self._bash_executor:
            self._bash_executor.close()

    async def __aenter__(self):
        """Start using this task service"""
        # No special initialization needed for bash task service
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        """Finish using this task service"""
        await self.close()


_bash_task_service: BashTaskService | None = None


def get_default_bash_task_service() -> BashTaskService:
    """Get the default bash task service instance."""
    global _bash_task_service
    if _bash_task_service:
        return _bash_task_service

    from openhands.agent_server.config import get_default_config

    config = get_default_config()
    _bash_task_service = BashTaskService(working_dir=config.workspace_path)
    return _bash_task_service
