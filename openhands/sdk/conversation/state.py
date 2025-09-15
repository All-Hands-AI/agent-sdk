# state.py
import json
from enum import Enum
from threading import RLock, get_ident
from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel, Field, PrivateAttr

from openhands.sdk.agent.base import AgentType
from openhands.sdk.conversation.event_store import EventLog
from openhands.sdk.conversation.persistence_const import BASE_STATE, EVENTS_DIR
from openhands.sdk.conversation.secrets_manager import SecretsManager
from openhands.sdk.event import Event
from openhands.sdk.io import FileStore, InMemoryFileStore
from openhands.sdk.logger import get_logger
from openhands.sdk.utils.protocol import ListLike


logger = get_logger(__name__)


class AgentExecutionState(str, Enum):
    """Enum representing the current execution state of the agent."""

    IDLE = "idle"  # Agent is ready to receive tasks
    RUNNING = "running"  # Agent is actively processing
    PAUSED = "paused"  # Agent execution is paused by user
    WAITING_FOR_CONFIRMATION = (
        "waiting_for_confirmation"  # Agent is waiting for user confirmation
    )
    FINISHED = "finished"  # Agent has completed the current task
    ERROR = "error"  # Agent encountered an error (optional for future use)


if TYPE_CHECKING:
    from openhands.sdk.conversation.secrets_manager import SecretsManager


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

    # New enum-based state management
    agent_state: AgentExecutionState = Field(default=AgentExecutionState.IDLE)
    confirmation_mode: bool = Field(
        default=False
    )  # Keep this as it's a configuration setting

    # Legacy boolean fields - kept for backward compatibility during transition
    agent_finished: bool = Field(default=False)
    agent_waiting_for_confirmation: bool = Field(default=False)
    agent_paused: bool = Field(default=False)

    activated_knowledge_microagents: list[str] = Field(
        default_factory=list,
        description="List of activated knowledge microagents name",
    )

    # ===== Private attrs (NOT Fields) =====
    _lock: RLock = PrivateAttr(default_factory=RLock)
    _syncing: bool = PrivateAttr(default=False)
    _owner_tid: Optional[int] = PrivateAttr(default=None)
    _secrets_manager: "SecretsManager" = PrivateAttr(default_factory=SecretsManager)
    _fs: FileStore = PrivateAttr()  # filestore for persistence
    _events: EventLog = PrivateAttr()  # now the storage for events
    _autosave_enabled: bool = PrivateAttr(
        default=False
    )  # to avoid recursion during init

    # ===== Public "events" facade (ListLike[Event]) =====
    @property
    def events(self) -> ListLike[Event]:
        return self._events

    # ===== State synchronization methods =====
    def _sync_boolean_fields_from_enum(self) -> None:
        """Synchronize legacy boolean fields with the enum state."""
        if self._syncing:
            return
        self._syncing = True
        try:
            self.agent_finished = self.agent_state == AgentExecutionState.FINISHED
            self.agent_waiting_for_confirmation = (
                self.agent_state == AgentExecutionState.WAITING_FOR_CONFIRMATION
            )
            self.agent_paused = self.agent_state == AgentExecutionState.PAUSED
        finally:
            self._syncing = False

    def _sync_enum_from_boolean_fields(self) -> None:
        """Synchronize enum state with legacy boolean fields (for backward compatibility)."""  # noqa: E501
        if self._syncing:
            return
        self._syncing = True
        try:
            if self.agent_finished:
                self.agent_state = AgentExecutionState.FINISHED
            elif self.agent_waiting_for_confirmation:
                self.agent_state = AgentExecutionState.WAITING_FOR_CONFIRMATION
            elif self.agent_paused:
                self.agent_state = AgentExecutionState.PAUSED
            else:
                # Default to IDLE if no flags are set
                self.agent_state = AgentExecutionState.IDLE
        finally:
            self._syncing = False

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

    @property
    def secrets_manager(self) -> SecretsManager:
        """Public accessor for the SecretsManager (stored as a private attr)."""
        return self._secrets_manager

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

            # Reconcile agent config with deserialized one
            resolved = agent.resolve_diff_from_deserialized(state.agent)

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

    # ===== Auto-persist base on public field changes =====
    def __setattr__(self, name, value):
        # Handle state synchronization first
        if name == "agent_state" and hasattr(self, "agent_state"):
            # When enum state changes, sync boolean fields
            super().__setattr__(name, value)
            if hasattr(self, "_autosave_enabled"):  # Avoid sync during init
                self._sync_boolean_fields_from_enum()
        elif name in [
            "agent_finished",
            "agent_waiting_for_confirmation",
            "agent_paused",
        ] and hasattr(self, "agent_state"):
            # When boolean fields change, sync enum state
            super().__setattr__(name, value)
            if hasattr(self, "_autosave_enabled"):  # Avoid sync during init
                self._sync_enum_from_boolean_fields()
        else:
            super().__setattr__(name, value)

        # Only autosave when:
        # - autosave is enabled (set post-init)
        # - the attribute is a *public field* (not a PrivateAttr)
        # - we have a filestore to write to
        is_field = name in self.__class__.model_fields
        autosave_enabled = getattr(self, "_autosave_enabled", False)
        fs = getattr(self, "_fs", None)

        if autosave_enabled and is_field and fs is not None:
            try:
                self._save_base_state(fs)
            except Exception as e:
                logger.exception("Auto-persist base_state failed", exc_info=True)
                raise e
