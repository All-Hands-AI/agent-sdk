import asyncio
import glob
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from uuid import UUID

from openhands.agent_server.models import (
    BashCommand,
    BashEventBase,
    BashEventPage,
    BashEventSortOrder,
    BashOutput,
    ExecuteBashRequest,
)
from openhands.agent_server.pub_sub import PubSub, Subscriber
from openhands.sdk.logger import get_logger
from openhands.sdk.utils.shell_execution import (
    ShellOutput,
    execute_shell_command,
)


logger = get_logger(__name__)
MAX_CONTENT_CHAR_LENGTH = 1024 * 1024


@dataclass
class BashEventService:
    """Service for executing bash events which are not added to the event stream and
    will not be visible to the agent."""

    bash_events_dir: Path = field()
    _pub_sub: PubSub[BashEventBase] = field(
        default_factory=lambda: PubSub[BashEventBase](), init=False
    )

    def _ensure_bash_events_dir(self) -> None:
        """Ensure the bash events directory exists."""
        self.bash_events_dir.mkdir(parents=True, exist_ok=True)

    def _timestamp_to_str(self, timestamp: datetime) -> str:
        result = timestamp.strftime("%Y%m%d%H%M%S")
        return result

    def _get_event_filename(self, event: BashEventBase) -> str:
        """Generate filename using YYYYMMDDHHMMSS_eventId_actionId format."""
        result = [self._timestamp_to_str(event.timestamp), event.kind]
        command_id = getattr(event, "command_id", None)
        if command_id:
            result.append(command_id.hex)
        result.append(event.id.hex)
        return "_".join(result)

    def _save_event_to_file(self, event: BashEventBase) -> None:
        """Save an event to a file."""
        self._ensure_bash_events_dir()
        filename = self._get_event_filename(event)
        filepath = self.bash_events_dir / filename

        with open(filepath, "w") as f:
            # Use model_dump with mode='json' to handle UUID serialization
            data = event.model_dump(mode="json")
            f.write(json.dumps(data, indent=2))

    def _load_event_from_file(self, filepath: Path) -> BashEventBase | None:
        """Load an event from a file."""
        try:
            json_data = filepath.read_text()
            return BashEventBase.model_validate_json(json_data)
        except Exception as e:
            logger.error(f"Error loading event from {filepath}: {e}")
            return None

    def _get_event_files_by_pattern(self, pattern: str) -> list[Path]:
        """Get event files matching a glob pattern, sorted by timestamp."""
        self._ensure_bash_events_dir()
        files = glob.glob(str(self.bash_events_dir / pattern))
        return sorted([Path(f) for f in files])

    async def get_bash_event(self, event_id: str) -> BashEventBase | None:
        """Get the event with the id given, or None if there was no such event."""
        # Use glob pattern to find files ending with the event_id
        pattern = f"*_{event_id}"
        files = self._get_event_files_by_pattern(pattern)

        if not files:
            return None

        # Load and return the first matching event
        return self._load_event_from_file(files[0])

    async def batch_get_bash_events(
        self, event_ids: list[str]
    ) -> list[BashEventBase | None]:
        """Given a list of ids, get bash events (Or none for any which were
        not found)"""
        results = []
        for event_id in event_ids:
            result = await self.get_bash_event(event_id)
            results.append(result)
        return results

    async def search_bash_events(
        self,
        kind__eq: str | None = None,
        command_id__eq: UUID | None = None,
        timestamp__gte: datetime | None = None,
        timestamp__lt: datetime | None = None,
        sort_order: BashEventSortOrder = BashEventSortOrder.TIMESTAMP,
        page_id: str | None = None,
        limit: int = 100,
    ) -> BashEventPage:
        """Search for events. If an command_id is given, only the observations for the
        action are returned."""

        # Build the search pattern - we start with a wildcard as we don't
        # exact match timestamps and filter later
        search_pattern = ["*"]
        if kind__eq:
            search_pattern.append(f"_{kind__eq}_*")
        if command_id__eq:
            search_pattern.append(f"_{command_id__eq.hex}_*")

        files = self._get_event_files_by_pattern("".join(search_pattern))
        files.sort(
            key=lambda f: f.name,
            reverse=(sort_order == BashEventSortOrder.TIMESTAMP_DESC),
        )

        # Timestamp filtering.
        if timestamp__gte:
            timestamp_gte_str = self._timestamp_to_str(timestamp__gte)
            files = [file for file in files if file.name >= timestamp_gte_str]
        if timestamp__lt:
            timestamp_lt_str = self._timestamp_to_str(timestamp__lt)
            files = [file for file in files if file.name < timestamp_lt_str]

        # Handle pagination
        page_files = []
        start_index = 0

        # Find the starting point if page_id is provided
        if page_id:
            for i, file in enumerate(files):
                if str(file.name) == page_id:
                    start_index = i
                    break

        # Collect items for this page
        next_page_id = None
        for i in range(start_index, len(files)):
            if len(files) >= limit:
                # We have more items, set next_page_id
                if i < len(files):
                    next_page_id = str(files[i].name)
                break
            page_files.append(files[i])

        # Load all events from files
        page_events = []
        for file_path in files:
            event = self._load_event_from_file(file_path)
            if event is not None:
                page_events.append(event)

        return BashEventPage(items=page_events, next_page_id=next_page_id)

    async def start_bash_command(
        self, request: ExecuteBashRequest
    ) -> tuple[BashCommand, asyncio.Task]:
        """Execute a bash command. The output will be published separately."""
        command = BashCommand(**request.model_dump())
        self._save_event_to_file(command)
        await self._pub_sub(command)

        # Execute the bash command in a background task
        task = asyncio.create_task(self._execute_bash_command(command))

        return command, task

    async def _execute_bash_command(self, command: BashCommand) -> None:
        """Execute the bash event and create an observation event."""
        output_order = 0

        def output_callback(shell_output: ShellOutput):
            nonlocal output_order
            # Create and publish BashOutput event
            bash_output = BashOutput(
                command_id=command.id,
                order=shell_output.order
                if shell_output.order is not None
                else output_order,
                stdout=shell_output.stdout,
                stderr=shell_output.stderr,
                exit_code=shell_output.exit_code,
            )

            self._save_event_to_file(bash_output)
            # Note: We need to use asyncio.create_task to handle the async pub_sub call
            # within the synchronous callback
            asyncio.create_task(self._pub_sub(bash_output))
            output_order += 1

        try:
            # Use the shared shell execution utility
            await execute_shell_command(
                command=command.command,
                cwd=command.cwd,
                timeout=command.timeout,
                output_callback=output_callback,
            )

            # The output_callback handles all the output events, including the final one
            # with the exit code, so we don't need to create additional events here

        except Exception as e:
            logger.error(f"Error executing bash command '{command.command}': {e}")
            # Create error output event
            error_output = BashOutput(
                command_id=command.id,
                order=0,
                exit_code=-1,
                stderr=f"Error executing command: {str(e)}",
            )

            self._save_event_to_file(error_output)
            await self._pub_sub(error_output)

    async def subscribe_to_events(self, subscriber: Subscriber[BashEventBase]) -> UUID:
        """Subscribe to bash events.

        The subscriber will receive BashEventBase instances.
        """
        return self._pub_sub.subscribe(subscriber)

    async def unsubscribe_from_events(self, subscriber_id: UUID) -> bool:
        return self._pub_sub.unsubscribe(subscriber_id)

    async def clear_all_events(self) -> int:
        """Clear all bash events from storage.

        Returns:
            int: The number of events that were cleared.
        """
        self._ensure_bash_events_dir()

        # Get all event files
        files = self._get_event_files_by_pattern("*")

        # Count files before deletion
        count = len(files)

        # Remove all event files
        for file_path in files:
            try:
                file_path.unlink()
            except Exception as e:
                logger.error(f"Error deleting event file {file_path}: {e}")

        logger.info(f"Cleared {count} bash events from storage")
        return count

    async def close(self):
        """Close the bash event service and clean up resources."""
        await self._pub_sub.close()

    async def __aenter__(self):
        """Start using this task service"""
        # No special initialization needed for bash event service
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        """Finish using this task service"""
        await self.close()


_bash_event_service: BashEventService | None = None


def get_default_bash_event_service() -> BashEventService:
    """Get the default bash event service instance."""
    global _bash_event_service
    if _bash_event_service:
        return _bash_event_service

    from openhands.agent_server.config import get_default_config

    config = get_default_config()
    _bash_event_service = BashEventService(bash_events_dir=config.bash_events_dir)
    return _bash_event_service
