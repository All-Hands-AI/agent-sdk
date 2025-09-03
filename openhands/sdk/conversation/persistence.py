import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from .conversation import Conversation  # noqa

from openhands.sdk.event import EventType
from openhands.sdk.io import FileStore, LocalFileStore
from openhands.sdk.logger import get_logger


logger = get_logger(__name__)

INDEX_WIDTH = 4
EVENTS_DIR_NAME = "events"
BASE_STATE_NAME = "base_state.json"


class ConversationPersistence:
    """
    Simple persistence for conversations using raw events.

    Layout under `root/`:
      - base_state.json                     # state without events
      - events/<index>-<ts>.jsonl           # raw events, one per file

    Conventions:
      - <index> is zero-padded to INDEX_WIDTH
      - <ts> is UTC: YYYYMMDDTHHMMSS
    """

    _RE_INDIV = re.compile(r"^(?P<idx>\d+)-(?P<ts>\d{8}T\d{6})\.jsonl$")

    def save(
        self, obj: "Conversation", dir_path: str, filestore: FileStore | None = None
    ) -> None:
        """Save conversation state and events."""
        filestore = filestore or LocalFileStore(root=dir_path)

        with obj.state:
            # Save base state without events
            self._write_base_state(obj, filestore)

            # Save only new events
            saved_indices = self._saved_indices(filestore)
            for idx, event in enumerate(obj.state.events):
                if idx not in saved_indices:
                    self._write_event(idx, event, filestore)

    def load(
        self, dir_path: str, agent, file_store: FileStore | None = None, **kwargs
    ) -> "Conversation":
        """Load conversation state and events."""
        from .conversation import Conversation
        from .state import ConversationState

        filestore = file_store or LocalFileStore(root=dir_path)

        # Load base state
        base_state_dict = json.loads(filestore.read(BASE_STATE_NAME))
        obj = Conversation(agent=agent, **kwargs)

        with obj.state:
            obj.state = ConversationState.model_validate(base_state_dict)

            # Load events
            event_entries = []
            for path in filestore.list(EVENTS_DIR_NAME):
                name = os.path.basename(path)
                match = self._RE_INDIV.match(name)
                if match:
                    event_entries.append((int(match.group("idx")), path))

            # Load events in order
            event_entries.sort(key=lambda t: t[0])
            for _, path in event_entries:
                blob = filestore.read(path)
                for line in blob.splitlines():
                    if line:
                        event_dict = json.loads(line)
                        try:
                            event = self._deserialize_event(event_dict)
                            obj.state.events.append(event)  # type: ignore
                        except Exception as e:
                            logger.error(
                                f"Failed to deserialize event from {path}: {e}"
                            )

        return obj

    def _write_base_state(self, obj: "Conversation", file_store: FileStore) -> None:
        """Write base state without events."""
        base = obj.state.model_copy()
        base.events = []
        data = json.dumps(
            base.model_dump(), ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        file_store.write(BASE_STATE_NAME, data)

    def _write_event(self, index: int, event: EventType, file_store: FileStore) -> None:
        """Write a single event to file."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        name = f"{index:0{INDEX_WIDTH}d}-{ts}.jsonl"
        path = str(Path(EVENTS_DIR_NAME) / name)

        line = (
            json.dumps(event.model_dump(), ensure_ascii=False, separators=(",", ":"))
            + "\n"
        ).encode("utf-8")
        file_store.write(path, line)

    def _saved_indices(self, file_store: FileStore) -> set[int]:
        """Get indices of already saved events."""
        saved = set()
        for path in file_store.list(EVENTS_DIR_NAME):
            name = os.path.basename(path)
            match = self._RE_INDIV.match(name)
            if match:
                saved.add(int(match.group("idx")))
        return saved

    def _deserialize_event(self, event_dict: dict) -> EventType:
        """Deserialize an event dictionary back to an EventType instance."""
        from openhands.sdk.event import (
            ActionEvent,
            AgentErrorEvent,
            MessageEvent,
            ObservationEvent,
            SystemPromptEvent,
        )

        # Map event kind to event class
        event_classes = {
            "action": ActionEvent,
            "observation": ObservationEvent,
            "message": MessageEvent,
            "system_prompt": SystemPromptEvent,
            "agent_error": AgentErrorEvent,
        }

        kind = event_dict.get("kind")
        if kind in event_classes:
            return event_classes[kind].model_validate(event_dict)
        else:
            # For unknown event types, log warning and skip
            logger.warning(f"Unknown event kind '{kind}', skipping event")
            raise ValueError(f"Unknown event kind: {kind}")
