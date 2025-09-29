# state.py
import json
from enum import Enum
from typing import TYPE_CHECKING

from pydantic import Field, PrivateAttr

from openhands.sdk.agent.base import AgentBase
from openhands.sdk.conversation.conversation_stats import ConversationStats
from openhands.sdk.conversation.event_store import EventLog
from openhands.sdk.conversation.fifo_lock import FIFOLock
from openhands.sdk.conversation.persistence_const import BASE_STATE, EVENTS_DIR
from openhands.sdk.conversation.secrets_manager import SecretsManager
from openhands.sdk.conversation.types import ConversationID
from openhands.sdk.event import ActionEvent, ObservationEvent, UserRejectObservation
from openhands.sdk.event.base import EventBase
from openhands.sdk.io import FileStore, InMemoryFileStore
from openhands.sdk.logger import get_logger
from openhands.sdk.security.confirmation_policy import (
    ConfirmationPolicyBase,
    NeverConfirm,
)
from openhands.sdk.utils.models import OpenHandsModel
from openhands.sdk.utils.protocol import ListLike


logger = get_logger(__name__)


class AgentExecutionStatus(str, Enum):
    """Enum representing the current execution state of the agent."""

    IDLE = "idle"  # Agent is ready to receive tasks
    RUNNING = "running"  # Agent is actively processing
    PAUSED = "paused"  # Agent execution is paused by user
    WAITING_FOR_CONFIRMATION = (
        "waiting_for_confirmation"  # Agent is waiting for user confirmation
    )
    FINISHED = "finished"  # Agent has completed the current task
    ERROR = "error"  # Agent encountered an error (optional for future use)
    STUCK = "stuck"  # Agent is stuck in a loop or unable to proceed


if TYPE_CHECKING:
    from openhands.sdk.conversation.secrets_manager import SecretsManager


class ConversationState(OpenHandsModel, FIFOLock):
    # ===== Public, validated fields =====
    id: ConversationID = Field(description="Unique conversation ID")

    agent: AgentBase = Field(
        ...,
        description=(
            "The agent running in the conversation. "
            "This is persisted to allow resuming conversations and "
            "check agent configuration to handle e.g., tool changes, "
            "LLM changes, etc."
        ),
    )
    max_iterations: int = Field(
        default=500,
        gt=0,
        description="Maximum number of iterations the agent can "
        "perform in a single run.",
    )
    stuck_detection: bool = Field(
        default=True,
        description="Whether to enable stuck detection for the agent.",
    )

    # Enum-based state management
    agent_status: AgentExecutionStatus = Field(default=AgentExecutionStatus.IDLE)
    confirmation_policy: ConfirmationPolicyBase = NeverConfirm()

    activated_knowledge_microagents: list[str] = Field(
        default_factory=list,
        description="List of activated knowledge microagents name",
    )

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
        max_iterations: int = 500,
        stuck_detection: bool = True,
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
