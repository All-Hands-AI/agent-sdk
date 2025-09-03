import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError


if TYPE_CHECKING:
    from .conversation import Conversation  # noqa

from openhands.core.io import FileStore, LocalFileStore
from openhands.sdk.event import EventBase, EventType
from openhands.sdk.logger import get_logger


logger = get_logger(__name__)


INDEX_WIDTH = 4
MESSAGE_DIR_NAME = "messages"
EVENTS_DIR_NAME = "events"
BASE_STATE_NAME = "base_state.json"


class ConversationPersistence:
    """
    Layout under `root/`:
      - base_state.json                     # small JSON (without events)
      - events/<index>-<ts>.jsonl           # ALL events, one event per file
      - messages/<index>-<ts>.jsonl         # legacy format (backward compatibility)

    Conventions:
      - <index> is zero-padded to `cfg.index_width`
      - <ts> is UTC: YYYYMMDDTHHMMSS
    """

    _RE_INDIV = re.compile(r"^(?P<idx>\d+)-(?P<ts>\d{8}T\d{6})\.jsonl$")

    # ---------- Public API ----------

    def save(
        self, obj: "Conversation", dir_path: str, filestore: FileStore | None = None
    ) -> None:
        """
        Persist `obj.state` into `dir_path`:
          - overwrite base_state.json each call (it’s small)
          - save ALL events to events/ directory
          - enumerate existing event files to see which indices are already saved
          - write new files for missing indices
        """
        filestore = filestore or LocalFileStore(root=dir_path)
        # Use keys relative to the filestore root
        base_path = BASE_STATE_NAME
        events_dir = EVENTS_DIR_NAME

        with obj.state:
            # 1) write base_state (without events)
            self._write_base_state(base_path, obj, filestore)

            # 2) save ALL events
            saved_event_indices = self._saved_indices(events_dir, filestore)
            for idx, event in enumerate(obj.state.events):
                if idx in saved_event_indices:
                    continue
                self._write_individual(events_dir, idx, event, filestore)

    def load(
        self, dir_path: str, agent, file_store: FileStore | None = None, **kwargs
    ) -> "Conversation":
        """
        Restore a Conversation instance from `dir_path`:
          - read base_state.json
          - try to load from events/ directory first (new format)
          - fall back to messages/ directory for backward compatibility
        """
        # Lazy imports to avoid circular imports
        from openhands.sdk.event import MessageEvent
        from openhands.sdk.llm import Message

        from .conversation import Conversation
        from .state import ConversationState

        filestore = file_store or LocalFileStore(root=dir_path)
        base_path = BASE_STATE_NAME

        base_state_dict = json.loads(filestore.read(base_path))

        obj: "Conversation" = Conversation(agent=agent, **kwargs)
        with obj.state:
            obj.state = ConversationState.model_validate(base_state_dict)

            events_dir = EVENTS_DIR_NAME
            msg_dir = MESSAGE_DIR_NAME

            # Try to load from events directory first (new format with ALL events)
            events_entries: list[tuple[int, str]] = []
            for p in filestore.list(events_dir):
                name = os.path.basename(p)
                m = self._RE_INDIV.match(name)
                if m:
                    events_entries.append((int(m.group("idx")), p))

            if events_entries:
                # Load from events directory (new format)
                events_entries.sort(key=lambda t: t[0])
                for _, path in events_entries:
                    blob = filestore.read(path)
                    for line in blob.splitlines():
                        if not line:
                            continue
                        event_dict = json.loads(line)
                        try:
                            # Deserialize the event based on its type
                            event = self._deserialize_event(event_dict)
                            # Type cast needed because EventBase is not in EventType
                            # union but we want to support future non-LLMConvertible
                            # Event types
                            obj.state.events.append(event)  # type: ignore
                        except Exception as e:
                            logger.error(
                                f"Failed to deserialize event from {path}: {e}"
                            )
            else:
                # Fall back to messages directory (backward compatibility)
                msg_entries: list[tuple[int, str]] = []
                for p in filestore.list(msg_dir):
                    name = os.path.basename(p)
                    m = self._RE_INDIV.match(name)
                    if m:
                        msg_entries.append((int(m.group("idx")), p))
                msg_entries.sort(key=lambda t: t[0])

                # append messages in order as MessageEvent(s)
                for _, path in msg_entries:
                    blob = filestore.read(path)
                    for line in blob.splitlines():
                        if not line:
                            continue
                        msg_dict = json.loads(line)
                        try:
                            message = Message.model_validate(msg_dict)
                            role = message.role
                            if role == "user":
                                source = "user"
                            elif role == "assistant" or role == "system":
                                source = "agent"
                            elif role == "tool":
                                source = "environment"
                            else:
                                source = "agent"
                            obj.state.events.append(
                                MessageEvent(source=source, llm_message=message)
                            )
                        except ValidationError as e:
                            logger.error(f"Failed to validate message from {path}: {e}")
        return obj

    # ---------- Internals ----------

    def _write_base_state(
        self,
        base_path: str,
        obj: "Conversation",
        file_store: FileStore,
    ) -> None:
        base = obj.state.model_copy()
        # Remove events for compact base state
        base.events = []
        data = json.dumps(
            base.model_dump(), ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        file_store.write(base_path, data)

    def _write_individual(
        self, msg_dir: str, index: int, msg_model: Any, file_store: FileStore
    ) -> None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        name = f"{index:0{INDEX_WIDTH}d}-{ts}.jsonl"
        path = self._join(msg_dir, name)
        line = (
            json.dumps(
                msg_model.model_dump(), ensure_ascii=False, separators=(",", ":")
            )
            + "\n"
        ).encode("utf-8")
        file_store.write(path, line)

    def _saved_indices(self, msg_dir: str, file_store: FileStore) -> set[int]:
        saved: set[int] = set()
        for p in file_store.list(msg_dir):
            name = os.path.basename(p)
            m = self._RE_INDIV.match(name)
            if m:
                saved.add(int(m.group("idx")))
        return saved

    def _deserialize_event(self, event_dict: dict) -> EventType | EventBase:
        """Deserialize an event dictionary back to an EventType instance."""
        from openhands.sdk.event import (
            ActionEvent,
            AgentErrorEvent,
            EventBase,
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
            event_class = event_classes[kind]
            return event_class.model_validate(event_dict)
        else:
            # For unknown event types, try to deserialize as generic EventBase
            # This provides forward compatibility for new event types
            logger.warning(
                f"Unknown event kind '{kind}', deserializing as generic EventBase"
            )
            return EventBase.model_validate(event_dict)

    @staticmethod
    def _join(prefix: str, *parts: str) -> str:
        return str(Path(prefix).joinpath(*parts))
