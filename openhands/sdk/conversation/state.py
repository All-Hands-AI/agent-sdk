# state.py
import json
import uuid
from threading import RLock, get_ident
from typing import Optional

from pydantic import BaseModel, Field, PrivateAttr

from openhands.sdk.agent.base import AgentType
from openhands.sdk.conversation.event_store import EventLog
from openhands.sdk.conversation.persistence_const import BASE_STATE, EVENTS_DIR
from openhands.sdk.io import FileStore, InMemoryFileStore
from openhands.sdk.logger import get_logger


logger = get_logger(__name__)


class ConversationState(BaseModel):
    # ===== Public, validated fields =====
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique conversation ID",
    )

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
    _fs: FileStore = PrivateAttr()  # filestore for persistence
    _events: EventLog = PrivateAttr()  # now the storage for events
    _autosave_enabled: bool = PrivateAttr(
        default=False
    )  # to avoid recursion during init

    # ===== Public "events" facade (ListLike[Event]) =====
    @property
    def events(self) -> EventLog:
        return self._events

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

    # ===== Base snapshot helpers (same FileStore usage you had) =====
    def _save_base_state(self, fs: FileStore) -> None:
        """
        Persist base state snapshot (no events; events are file-backed).
        """
        payload = self.model_dump_json(exclude_none=True)
        fs.write(BASE_STATE, payload)

    # ===== Factory: open-or-create (no load/save methods needed) =====
    @classmethod
    def create(
        cls: type["ConversationState"],
        id: str,
        agent: AgentType,
        file_store: FileStore | None = None,
    ) -> "ConversationState":
        """
        If base_state.json exists: resume (attach EventLog).
        Else: create fresh (agent required), persist base, and return.
        """
        if file_store is None:
            file_store = InMemoryFileStore()
        else:
            base_txt = file_store.read(BASE_STATE)
            if base_txt:
                state = cls.model_validate(json.loads(base_txt))
                state._fs = file_store
                state._events = EventLog(file_store, dir_path=EVENTS_DIR)
                state._autosave_enabled = True
                return state

        if agent is None:
            raise ValueError(
                "agent is required when initializing a new ConversationState"
            )

        state = cls(id=id, agent=agent)
        state._fs = file_store
        state._events = EventLog(file_store, dir_path=EVENTS_DIR)
        state._save_base_state(file_store)  # initial snapshot
        state._autosave_enabled = True
        return state

    # ===== Auto-persist base on public field changes =====
    def __setattr__(self, name, value):
        # Only autosave when:
        # - autosave is enabled (set post-init)
        # - the attribute is a *public field* (not a PrivateAttr)
        # - we have a filestore to write to
        is_field = name in self.__class__.model_fields
        autosave_enabled = getattr(self, "_autosave_enabled", False)
        fs = getattr(self, "_fs", None)

        if not (autosave_enabled and is_field and fs is not None):
            return super().__setattr__(name, value)

        _sentinel = object()
        old = getattr(self, name, _sentinel)
        super().__setattr__(name, value)

        if old is _sentinel or old != value:
            try:
                self._save_base_state(fs)
            except Exception as e:
                logger.exception("Auto-persist base_state failed", exc_info=True)
                raise e
