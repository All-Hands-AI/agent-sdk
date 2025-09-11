# state.py
import json
from typing import Iterator

from openhands.sdk.conversation.persistence_const import (
    EVENT_FILE_PATTERN,
    EVENT_NAME_RE,
    EVENTS_DIR,
)
from openhands.sdk.event import Event, EventBase
from openhands.sdk.io import FileStore
from openhands.sdk.logger import get_logger
from openhands.sdk.utils.protocol import ListLike


logger = get_logger(__name__)


class EventLog(ListLike[Event]):
    def __init__(self, fs: FileStore, dir_path: str = EVENTS_DIR) -> None:
        self._fs = fs
        self._dir = dir_path
        self._id_to_idx: dict[str, int] = {}
        self._idx_to_id: dict[int, str] = {}
        self._idx_to_path: dict[int, str] = {}  # Store actual file paths
        self._length = self._scan_and_build_index()

    def get_index(self, event_id: str) -> int:
        """Return the integer index for a given event_id."""
        try:
            return self._id_to_idx[event_id]
        except KeyError:
            raise KeyError(f"Unknown event_id: {event_id}")

    def get_id(self, idx: int) -> str:
        """Return the event_id for a given index."""
        if idx < 0:
            idx += self._length
        if idx < 0 or idx >= self._length:
            raise IndexError("Event index out of range")
        return self._idx_to_id[idx]

    def __getitem__(self, idx: int) -> Event:
        if idx < 0:
            idx += self._length
        if idx < 0 or idx >= self._length:
            raise IndexError("Event index out of range")
        txt = self._fs.read(self._path(idx))
        if not txt:
            raise FileNotFoundError(f"Missing event file: {self._path(idx)}")
        return EventBase.model_validate(json.loads(txt))

    def __iter__(self) -> Iterator[Event]:
        for i in range(self._length):
            txt = self._fs.read(self._path(i))
            if not txt:
                continue
            evt = EventBase.model_validate(json.loads(txt))
            evt_id = evt.id
            # only backfill mapping if missing
            if i not in self._idx_to_id:
                self._idx_to_id[i] = evt_id
                self._id_to_idx.setdefault(evt_id, i)
            yield evt

    def append(self, item: Event) -> None:
        evt_id = item.id
        expected_idx = self._length

        # Validate that event ID matches expected index position
        if evt_id in self._id_to_idx:
            existing_idx = self._id_to_idx[evt_id]
            if existing_idx != expected_idx:
                raise ValueError(
                    f"Event ID validation failed: Event with ID '{evt_id}' "
                    f"already exists at index {existing_idx}, but trying to append "
                    f"at index {expected_idx}. Event IDs must be unique and "
                    f"match their index position."
                )

        path = self._path(self._length, event_id=evt_id)
        self._fs.write(path, item.model_dump_json(exclude_none=True))
        self._idx_to_id[self._length] = evt_id
        self._id_to_idx[evt_id] = self._length
        # Store the filename for the new event
        filename = path.split("/")[-1]
        self._idx_to_path[self._length] = filename
        self._length += 1

    def __len__(self) -> int:
        return self._length

    def clear(self) -> None:
        """Clear all events from the log."""
        # Remove all event files
        for i in range(self._length):
            if i in self._idx_to_id:
                event_id = self._idx_to_id[i]
                path = self._path(i, event_id=event_id)
                if self._fs.exists(path):
                    self._fs.delete(path)

        # Reset internal state
        self._length = 0
        self._idx_to_id.clear()
        self._id_to_idx.clear()
        self._idx_to_path.clear()

    def _path(self, idx: int, *, event_id: str | None = None) -> str:
        # If we have the actual path stored (from scanning), use it
        if idx in self._idx_to_path:
            return f"{self._dir}/{self._idx_to_path[idx]}"

        # Otherwise, generate the new format path
        return f"{self._dir}/{
            EVENT_FILE_PATTERN.format(
                idx=idx, event_id=event_id or self._idx_to_id[idx]
            )
        }"

    def _scan_and_build_index(self) -> int:
        import re

        # Support both old format (event-00000.json) and new format
        # (event-00000-{id}.json)
        old_format_re = re.compile(r"^event-(?P<idx>\d{5})\.json$")

        try:
            paths = self._fs.list(self._dir)
        except Exception:
            self._id_to_idx.clear()
            self._idx_to_id.clear()
            return 0

        by_idx: dict[int, str] = {}
        path_by_idx: dict[int, str] = {}
        for p in paths:
            name = p.rsplit("/", 1)[-1]
            # Try new format first
            m = EVENT_NAME_RE.match(name)
            if m:
                idx = int(m.group("idx"))
                evt_id = m.group("event_id")
                by_idx[idx] = evt_id
                path_by_idx[idx] = name
            else:
                # Try old format for backward compatibility
                m = old_format_re.match(name)
                if m:
                    idx = int(m.group("idx"))
                    # For old format, we need to read the file to get the event ID
                    try:
                        import json

                        file_content = self._fs.read(f"{self._dir}/{name}")
                        if file_content:
                            event_data = json.loads(file_content)
                            evt_id = event_data.get("id", f"legacy-{idx}")
                            by_idx[idx] = evt_id
                            path_by_idx[idx] = name
                    except Exception:
                        # If we can't read the file, skip it
                        continue

        if not by_idx:
            self._id_to_idx.clear()
            self._idx_to_id.clear()
            self._idx_to_path.clear()
            return 0

        n = 0
        while True:
            if n not in by_idx:
                if any(i > n for i in by_idx.keys()):
                    logger.warning(
                        "Event index gap detected: "
                        f"expect next index {n} but got {sorted(by_idx.keys())}"
                    )
                break
            n += 1

        self._id_to_idx.clear()
        self._idx_to_id.clear()
        self._idx_to_path.clear()
        for i in range(n):
            evt_id = by_idx[i]
            self._idx_to_id[i] = evt_id
            self._id_to_idx.setdefault(evt_id, i)
            if i in path_by_idx:
                self._idx_to_path[i] = path_by_idx[i]
        return n
