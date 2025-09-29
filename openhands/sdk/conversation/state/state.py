# state.py
import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from pydantic import Field, PrivateAttr

from openhands.sdk.agent.base import AgentBase
from openhands.sdk.conversation.conversation_stats import ConversationStats
from openhands.sdk.conversation.event_store import EventLog
from openhands.sdk.conversation.fifo_lock import FIFOLock
from openhands.sdk.conversation.persistence_const import BASE_STATE, EVENTS_DIR
from openhands.sdk.conversation.secrets_manager import SecretsManager
from openhands.sdk.conversation.state.base import (
    ConversationBaseState,
)
from openhands.sdk.conversation.types import ConversationID
from openhands.sdk.event import ActionEvent, ObservationEvent, UserRejectObservation
from openhands.sdk.event.base import EventBase
from openhands.sdk.io import FileStore, InMemoryFileStore, LocalFileStore
from openhands.sdk.logger import get_logger
from openhands.sdk.utils.protocol import ListLike


logger = get_logger(__name__)


if TYPE_CHECKING:
    from openhands.sdk.conversation.secrets_manager import SecretsManager


class ConversationState(ConversationBaseState, FIFOLock):
    """Concrete class representing the full conversation state.

    Most fields are inherited from ConversationBaseState.
    """

    id: ConversationID = Field(description="Unique conversation ID")

    # Conversation statistics for LLM usage tracking
    stats: ConversationStats = Field(
        default_factory=ConversationStats,
        description="Conversation statistics for tracking LLM metrics",
    )

    # ===== Private attrs (NOT Fields) =====
    _secrets_manager: "SecretsManager" = PrivateAttr(default_factory=SecretsManager)
    _fs: FileStore = PrivateAttr()  # filestore for persistence
    _events: EventLog = PrivateAttr()  # now the storage for events
    _autosave_enabled: bool = PrivateAttr(
        default=False
    )  # to avoid recursion during init
    _on_state_change: Callable[[str, Any, Any], None] | None = PrivateAttr(
        default=None
    )  # callback for state changes

    def model_post_init(self, __context) -> None:
        """Initialize FIFOLock after Pydantic model initialization."""
        # Initialize FIFOLock
        FIFOLock.__init__(self)

    # ===== Public "events" facade (ListLike[Event]) =====
    @property
    def events(self) -> ListLike[EventBase]:
        return self._events

    @property
    def secrets_manager(self) -> SecretsManager:
        """Public accessor for the SecretsManager (stored as a private attr)."""
        return self._secrets_manager

    # ===== State change callback management =====
    def set_on_state_change(
        self, callback: Callable[[str, Any, Any], None] | None
    ) -> None:
        """
        Set a callback that will be called when any state field changes.

        Args:
            callback: Function that takes (field_name, old_value, new_value), or None
        """
        self._on_state_change = callback

    def _notify_state_change(
        self, field_name: str, old_value: Any, new_value: Any
    ) -> None:
        """
        Notify the registered callback about a state change.

        Args:
            field_name: Name of the field that changed
            old_value: Previous value of the field
            new_value: New value of the field
        """
        if self._on_state_change:
            try:
                self._on_state_change(field_name, old_value, new_value)
            except Exception as e:
                logger.exception(
                    f"State change callback failed for field '{field_name}': {e}",
                    exc_info=True,
                )

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
        id: ConversationID,
        agent: AgentBase,
        working_dir: str,
        persistence_dir: str | None = None,
        max_iterations: int = 500,
        stuck_detection: bool = True,
    ) -> "ConversationState":
        """
        If base_state.json exists: resume (attach EventLog,
            reconcile agent, enforce id).
        Else: create fresh (agent required), persist base, and return.
        """
        file_store = (
            LocalFileStore(persistence_dir) if persistence_dir else InMemoryFileStore()
        )

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

            state.stats = ConversationStats()

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

        state = cls(
            id=id,
            agent=agent,
            working_dir=working_dir,
            persistence_dir=persistence_dir,
            max_iterations=max_iterations,
            stuck_detection=stuck_detection,
        )
        state._fs = file_store
        state._events = EventLog(file_store, dir_path=EVENTS_DIR)
        state.stats = ConversationStats()

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
        # Only autosave when:
        # - autosave is enabled (set post-init)
        # - the attribute is a *public field* (not a PrivateAttr)
        # - we have a filestore to write to
        _sentinel = object()
        old = getattr(self, name, _sentinel)
        super().__setattr__(name, value)

        is_field = name in self.__class__.model_fields
        autosave_enabled = getattr(self, "_autosave_enabled", False)
        fs = getattr(self, "_fs", None)

        # Notify callback for field changes (even if autosave is disabled)
        if is_field and (old is _sentinel or old != value):
            # Only notify if we have a callback and this is not during initialization
            callback = getattr(self, "_on_state_change", None)
            if callback and autosave_enabled:  # Only notify after initialization
                self._notify_state_change(
                    name, old if old is not _sentinel else None, value
                )

        if not (autosave_enabled and is_field and fs is not None):
            return

        if old is _sentinel or old != value:
            try:
                self._save_base_state(fs)
            except Exception as e:
                logger.exception("Auto-persist base_state failed", exc_info=True)
                raise e

    @staticmethod
    def get_unmatched_actions(events: ListLike[EventBase]) -> list[ActionEvent]:
        """Find actions in the event history that don't have matching observations.

        This method identifies ActionEvents that don't have corresponding
        ObservationEvents or UserRejectObservations, which typically indicates
        actions that are pending confirmation or execution.

        Args:
            events: List of events to search through

        Returns:
            List of ActionEvent objects that don't have corresponding observations,
            in chronological order
        """
        observed_action_ids = set()
        unmatched_actions = []
        # Search in reverse - recent events are more likely to be unmatched
        for event in reversed(events):
            if isinstance(event, (ObservationEvent, UserRejectObservation)):
                observed_action_ids.add(event.action_id)
            elif isinstance(event, ActionEvent):
                if event.id not in observed_action_ids:
                    # Insert at beginning to maintain chronological order in result
                    unmatched_actions.insert(0, event)

        return unmatched_actions
