# state.py
import json
from typing import Iterator

from openhands.sdk.conversation.persistence_const import (
    EVENT_FILE_PATTERN,
    EVENT_ID_PATTERN,
    EVENT_NAME_RE,
    EVENTS_DIR,
)
from openhands.sdk.event import Event, EventBase
from openhands.sdk.io import FileStore
from openhands.sdk.logger import get_logger
from openhands.sdk.utils.protocol import ListLike


logger = get_logger(__name__)


# ===== Minimal file-backed, lazy EventLog that satisfies ListLike[Event] =====
class EventLog(ListLike[Event]):  # runtime class; conforms to the Protocol
    def __init__(self, fs: FileStore, dir_path: str = EVENTS_DIR) -> None:
        self._fs = fs
        self._dir = dir_path
        self._length = self._scan_len()  # contiguous count from 0..N-1

    def next_id(self) -> str:
        return EVENT_ID_PATTERN.format(idx=self._length)

    # ---- ListLike API ----
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
            try:
                yield EventBase.model_validate(json.loads(txt))
            except Exception as e:
                logger.error(
                    f"Failed to parse event file: {self._path(i)}", exc_info=True
                )
                raise e

    def append(self, item: Event) -> None:
        path = self._path(self._length)
        self._fs.write(path, item.model_dump_json(exclude_none=True))
        self._length += 1  # update length after successful write

    def __len__(self) -> int:
        return self._length

    # ---- internals ----
    def _path(self, idx: int) -> str:
        return f"{self._dir}/{EVENT_FILE_PATTERN.format(idx=idx)}"

    def _scan_len(self) -> int:
        try:
            paths = self._fs.list(self._dir)
        except Exception:
            return 0
        idxs: list[int] = []
        for p in paths:
            name = p.rsplit("/", 1)[-1]
            m = EVENT_NAME_RE.match(name)
            if m:
                idxs.append(int(m.group("idx")))
        if not idxs:
            return 0
        idxs.sort()
        n = 0
        for v in idxs:
            if v != n:
                logger.warning(f"Event index gap detected: expect next {n}, got {v}")
                break  # stop at first gap; we enforce contiguous indices
            n += 1
        return n
