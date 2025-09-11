# state.py
import json
import re
from threading import RLock, get_ident
from typing import Iterable, NamedTuple, Optional

from pydantic import BaseModel, Field, PrivateAttr

from openhands.sdk.agent.base import AgentType
from openhands.sdk.event import Event, EventBase
from openhands.sdk.io import FileStore
from openhands.sdk.logger import get_logger


logger = get_logger(__name__)


class EventFile(NamedTuple):
    idx: int
    path: str


BASE_STATE = "base_state.json"
AGENT_STATE = "agent_state.json"
EVENTS_DIR = "events"
_EVENT_NAME_RE = re.compile(r"^event-(?P<idx>\d{5})\.json$")
_EVENT_FILE_PATTERN = "event-{idx:05d}.json"


class ConversationState(BaseModel):
    # ===== Public, validated fields =====
    id: str = Field(description="Unique conversation ID")
    events: list[Event] = Field(default_factory=list)

    agent: AgentType = Field(
        ...,
        description=(
            "The agent running in the conversation. "
            "This is persisted to allow resuming conversations and "
            "check agent configuration to handle e.g., tool changes, "
            "LLM changes, etc."
        ),
    )

    # flags
    agent_finished: bool = Field(default=False)
    confirmation_mode: bool = Field(default=False)
    agent_waiting_for_confirmation: bool = Field(default=False)
    agent_paused: bool = Field(default=False)

    activated_knowledge_microagents: list[str] = Field(
        default_factory=list,
        description="List of activated knowledge microagents name",
    )

    # ===== Private attrs (NOT Fields) =====
    _lock: RLock = PrivateAttr(default_factory=RLock)
    _owner_tid: Optional[int] = PrivateAttr(default=None)

    # ===== Plain class vars (NOT Fields) =====
    EXCLUDE_FROM_BASE_STATE: tuple[str, ...] = ("events",)

    # ===== Lock/guard API =====
    def acquire(self) -> None:
        self._lock.acquire()
        self._owner_tid = get_ident()

    def release(self) -> None:
        self.assert_locked()
        self._owner_tid = None
        self._lock.release()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()

    def assert_locked(self) -> None:
        if self._owner_tid != get_ident():
            raise RuntimeError("State not held by current thread")

    # ===== Internal FS helpers (intentionally simple) =====

    @staticmethod
    def _scan_events(fs: FileStore) -> list[EventFile]:
        """
        Single directory listing for events. Returns (index, path) sorted.
        """
        try:
            paths = fs.list(EVENTS_DIR)
        except Exception:
            return []
        out: list[EventFile] = []
        for p in paths:
            name = p.rsplit("/", 1)[-1]
            m = _EVENT_NAME_RE.match(name)
            if m:
                out.append(EventFile(idx=int(m.group("idx")), path=p))
            else:
                logger.warning(f"Skipping unrecognized event file: {p}")
        out.sort(key=lambda t: t.idx)
        return out

    @staticmethod
    def _restore_from_files(
        fs: FileStore, files_sorted: Iterable[EventFile]
    ) -> list[Event]:
        """
        One pass: we already have the sorted file list; just read & parse.
        """
        out: list[Event] = []
        for _, path in files_sorted:
            txt = fs.read(path)
            if not txt:
                continue
            try:
                out.append(EventBase.model_validate(json.loads(txt)))
            except Exception:
                # Be strict if you want. Pragmatically, skip bad files.
                continue
        return out

    def _save_base_state(self, fs: FileStore) -> None:
        """
        Persist base state snapshot (excluding events).s
        """
        payload = self.model_dump_json(
            exclude_none=True,
            exclude=set(self.EXCLUDE_FROM_BASE_STATE),
        )
        fs.write(BASE_STATE, payload)

    # ===== Public Persistence API =====
    @classmethod
    def load(
        cls: type["ConversationState"], file_store: FileStore
    ) -> "ConversationState":
        """
        Load base snapshot (if any), then a SINGLE scan of events dir and replay.
        """
        # base
        base_txt = file_store.read(BASE_STATE)
        assert base_txt is not None
        state = cls.model_validate(json.loads(base_txt))

        # events (one list op, one pass decode)
        files_sorted = cls._scan_events(file_store)
        for ev in cls._restore_from_files(file_store, files_sorted):
            state.events.append(ev)
        return state

    def save(self, file_store: FileStore) -> None:
        """
        Persist current state:
        - Write base snapshot
        - Perform a SINGLE scan of events dir to find next index
        - Append any new events
        """
        # keep base snapshot current
        self._save_base_state(file_store)

        # single scan
        files_sorted = self._scan_events(file_store)
        next_idx = files_sorted[-1][0] + 1 if files_sorted else 0

        # append new events only
        if next_idx < len(self.events):
            for idx in range(next_idx, len(self.events)):
                event = self.events[idx]
                path = f"{EVENTS_DIR}/{_EVENT_FILE_PATTERN.format(idx=idx)}"
                file_store.write(path, event.model_dump_json(exclude_none=True))
