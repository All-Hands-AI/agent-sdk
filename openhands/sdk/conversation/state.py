# state.py
import json
from dataclasses import dataclass
from threading import RLock, get_ident
from typing import Optional

from pydantic import BaseModel, Field, PrivateAttr

from openhands.sdk.agent.base import AgentType
from openhands.sdk.conversation.event_store import EventLog
from openhands.sdk.conversation.persistence_const import (
    BASE_STATE,
    EVENT_NAME_RE,
    EVENTS_DIR,
)
from openhands.sdk.event import Event
from openhands.sdk.io import FileStore, InMemoryFileStore
from openhands.sdk.logger import get_logger
from openhands.sdk.utils.protocol import ListLike


logger = get_logger(__name__)


@dataclass
class EventFileInfo:
    """Information about an event file."""

    idx: int
    event_id: str
    path: str


class ConversationState(BaseModel):
    # ===== Public, validated fields =====
    id: str = Field(description="Unique conversation ID")

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

    # For backward compatibility with serialization
    serialized_events: list[dict] | None = Field(
        default=None,
        description="Events serialized for backward compatibility",
    )

    # ===== Private attrs (NOT Fields) =====
    _lock: RLock = PrivateAttr(default_factory=RLock)
    _owner_tid: Optional[int] = PrivateAttr(default=None)
    _fs: Optional[FileStore] = PrivateAttr(default=None)  # filestore for persistence
    _events: Optional[EventLog] = PrivateAttr(
        default=None
    )  # now the storage for events
    _autosave_enabled: bool = PrivateAttr(
        default=False
    )  # to avoid recursion during init

    def model_post_init(self, __context) -> None:
        """Initialize private attributes after model creation."""
        if self._fs is None:
            # For backward compatibility, create an in-memory file store
            from openhands.sdk.io import InMemoryFileStore

            self._fs = InMemoryFileStore()
        if self._events is None:
            self._events = EventLog(self._fs, dir_path=EVENTS_DIR)

        # Restore events from serialized_events if present
        if self.serialized_events:
            from openhands.sdk.event.base import EventBase

            for event_data in self.serialized_events:
                event = EventBase.model_validate(event_data)
                self._events.append(event)

    # ===== Public "events" facade (ListLike[Event]) =====
    @property
    def events(self) -> ListLike[Event]:
        if self._events is None:
            raise RuntimeError(
                "ConversationState not properly initialized - _events is None"
            )
        return self._events

    @events.setter
    def events(self, value: list[Event]) -> None:
        """Setter for backward compatibility with tests."""
        if self._events is None:
            raise RuntimeError(
                "ConversationState not properly initialized - _events is None"
            )
        # Clear existing events and add new ones
        self._events.clear()
        for event in value:
            self._events.append(event)

    def model_dump(self, **kwargs):
        """Override model_dump to include serialized_events for in-memory stores."""
        # First populate serialized_events if needed
        if self._events is not None:
            from openhands.sdk.io import InMemoryFileStore

            if isinstance(self._fs, InMemoryFileStore):
                self.serialized_events = [event.model_dump() for event in self._events]

        return super().model_dump(**kwargs)

    def model_dump_json(self, **kwargs):
        """Override model_dump_json to ensure serialized_events is populated."""
        # First populate serialized_events if needed
        if self._events is not None:
            from openhands.sdk.io import InMemoryFileStore

            if isinstance(self._fs, InMemoryFileStore):
                self.serialized_events = [event.model_dump() for event in self._events]

        return super().model_dump_json(**kwargs)

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
        payload = self.model_dump_json(exclude_none=True, exclude={"events"})
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
        If base_state.json exists: resume (attach EventLog,
            reconcile agent, enforce id).
        Else: create fresh (agent required), persist base, and return.
        """
        if file_store is None:
            file_store = InMemoryFileStore()

        try:
            base_text = file_store.read(BASE_STATE)
        except FileNotFoundError:
            base_text = None

        # ---- Resume path ----
        if base_text:
            state = cls.model_validate(json.loads(base_text))

            # Enforce conversation id match
            if state.id != id:
                raise ValueError(
                    f"Conversation ID mismatch: provided {id}, "
                    f"but persisted state has {state.id}"
                )

            # Reconcile agent config with deserialized one, then assert equality
            resolved = agent.resolve_diff_from_deserialized(state.agent)
            if agent.model_dump(exclude_none=True) != resolved.model_dump(
                exclude_none=True
            ):
                from openhands.sdk.utils.pydantic_diff import pretty_pydantic_diff

                raise ValueError(
                    "The agent provided is different from the one in persisted state. "
                    "Please use the same agent instance to resume the conversation.\n"
                    f"Diff: {pretty_pydantic_diff(agent, state.agent)}"
                )

            # Attach runtime handles and commit reconciled agent (may autosave)
            state._fs = file_store
            state._events = EventLog(file_store, dir_path=EVENTS_DIR)
            state._autosave_enabled = True
            state.agent = resolved

            logger.info(
                f"Resumed conversation {state.id} from persistent storage.\n"
                f"State: {state.model_dump(exclude={'agent'})}\n"
                f"Agent: {state.agent.model_dump_succint()}"
            )
            return state

        # ---- Fresh path ----
        if agent is None:
            raise ValueError(
                "agent is required when initializing a new ConversationState"
            )

        state = cls(id=id, agent=agent)
        state._fs = file_store
        state._events = EventLog(file_store, dir_path=EVENTS_DIR)
        state._save_base_state(file_store)  # initial snapshot
        state._autosave_enabled = True
        logger.info(
            f"Created new conversation {state.id}\n"
            f"State: {state.model_dump(exclude={'agent'})}\n"
            f"Agent: {state.agent.model_dump_succint()}"
        )
        return state

    # ===== Backward compatibility methods =====
    def save(self, file_store: FileStore) -> None:
        """Save state to file store (backward compatibility)."""
        self._save_base_state(file_store)

        # Also save events to the provided file store for backward compatibility
        if self._events is not None and len(self._events) > 0:
            # Create events directory if it doesn't exist
            if not file_store.exists(EVENTS_DIR):
                file_store.write(f"{EVENTS_DIR}/.keep", "")

            # Save each event to the file store
            for i, event in enumerate(self._events):
                event_filename = f"event-{i:05d}.json"
                event_path = f"{EVENTS_DIR}/{event_filename}"
                file_store.write(event_path, event.model_dump_json(exclude_none=True))

    @classmethod
    def load(
        cls,
        file_store: FileStore,
        id: str | None = None,
        agent: "AgentType | None" = None,
    ) -> "ConversationState":
        """Load state from file store (backward compatibility)."""
        # Check if there's persisted state
        if file_store.exists(BASE_STATE):
            base_state_data = file_store.read(BASE_STATE)
            base_state = json.loads(base_state_data)

            # If ID is provided, verify it matches the persisted state
            persisted_id = base_state.get("id")
            if id is not None and persisted_id != id:
                raise ValueError(
                    f"Provided ID {id} does not match persisted state ID {persisted_id}"
                )

            # Use persisted ID if none provided
            if id is None:
                id = persisted_id
                if id is None:
                    raise ValueError("No ID found in saved state and none provided")

            # Restore agent from saved state if none provided
            if agent is None:
                from openhands.sdk.agent.agent import Agent

                agent_data = base_state.get("agent")
                if agent_data is None:
                    raise ValueError("No agent found in saved state and none provided")
                agent = Agent.model_validate(agent_data)

            # Directly restore the state instead of calling create
            state = cls.model_validate(base_state)

            # Reconcile agent if provided
            if agent is not None:
                resolved = agent.resolve_diff_from_deserialized(state.agent)
                if agent.model_dump(exclude_none=True) != resolved.model_dump(
                    exclude_none=True
                ):
                    from openhands.sdk.utils.pydantic_diff import pretty_pydantic_diff

                    raise ValueError(
                        "The agent provided is different from the one in "
                        "persisted state. Please use the same agent instance "
                        "to resume the conversation.\n"
                        f"Diff: {pretty_pydantic_diff(agent, state.agent)}"
                    )
                state.agent = resolved

            # Attach runtime handles
            state._fs = file_store
            state._events = EventLog(file_store, dir_path=EVENTS_DIR)
            state._autosave_enabled = True

            return state
        else:
            # No persisted state - create new
            if id is None:
                raise ValueError("No saved state found and no ID provided")
            if agent is None:
                raise ValueError("No saved state found and no agent provided")
            return cls.create(id=id, agent=agent, file_store=file_store)

    @classmethod
    def _scan_events(cls, file_store: FileStore) -> list[EventFileInfo]:
        """Scan for event files (backward compatibility)."""
        import re

        # Support both old format (event-00000.json) and new format
        # (event-00000-{id}.json)
        old_format_re = re.compile(r"^event-(?P<idx>\d{5})\.json$")

        event_files = []
        if file_store.exists(EVENTS_DIR):
            for path in file_store.list(EVENTS_DIR):
                # Extract filename from path
                filename = path.split("/")[-1] if "/" in path else path

                # Try new format first
                match = EVENT_NAME_RE.match(filename)
                if match:
                    idx = int(match.group("idx"))
                    event_id = match.group("event_id")
                    event_files.append(
                        EventFileInfo(idx=idx, event_id=event_id, path=path)
                    )
                else:
                    # Try old format for backward compatibility
                    match = old_format_re.match(filename)
                    if match:
                        idx = int(match.group("idx"))
                        event_id = (
                            f"legacy-{idx}"  # Generate a fake event_id for old format
                        )
                        event_files.append(
                            EventFileInfo(idx=idx, event_id=event_id, path=path)
                        )
        return sorted(event_files, key=lambda x: x.idx)

    @classmethod
    def _restore_from_files(
        cls, file_store: FileStore, event_files: list[EventFileInfo]
    ) -> list[Event]:
        """Restore events from files (backward compatibility)."""
        events = []
        for event_file in event_files:
            file_path = (
                f"{EVENTS_DIR}/{event_file.path}"
                if not event_file.path.startswith(EVENTS_DIR)
                else event_file.path
            )
            if file_store.exists(file_path):
                content = file_store.read(file_path)
                try:
                    from openhands.sdk.event.base import EventBase

                    event_data = json.loads(content)
                    event = EventBase.model_validate(event_data)
                    events.append(event)
                except Exception:
                    # Skip corrupted events
                    continue
        return events

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
