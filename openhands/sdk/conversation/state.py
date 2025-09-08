import json
import uuid
from threading import RLock, get_ident
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from openhands.sdk.event import Event
from openhands.sdk.io import FileStore

from .persistence import (
    BASE_STATE,
    SHARD_SIZE,
    Manifest,
    _read_text,
)


class ConversationState(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,  # allow RLock in PrivateAttr
        validate_assignment=True,  # validate on attribute set
        frozen=False,
    )

    # Public, validated fields
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    events: list[Event] = Field(default_factory=list)
    agent_finished: bool = Field(default=False)
    confirmation_mode: bool = Field(default=False)
    agent_waiting_for_confirmation: bool = Field(default=False)
    agent_paused: bool = Field(default=False)
    activated_knowledge_microagents: list[str] = Field(
        default_factory=list, description="List of activated knowledge microagents name"
    )

    # Private attrs (NOT Fields) — allowed to start with underscore
    _lock: RLock = PrivateAttr(default_factory=RLock)
    _owner_tid: Optional[int] = PrivateAttr(default=None)
    _exclude_from_base_state: set[str] = {"events"}

    # Lock/guard API
    def acquire(self) -> None:
        self._lock.acquire()
        self._owner_tid = get_ident()

    def release(self) -> None:
        self._owner_tid = None
        self._lock.release()

    def __enter__(self) -> "ConversationState":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()

    def assert_locked(self) -> None:
        if self._owner_tid != get_ident():
            raise RuntimeError("State not held by current thread")

    # ====== Tiny public API requested ======

    def _save_base_state(self, fs: FileStore) -> None:
        """Persist base state snapshot (excluding events and other excluded fields)."""
        payload = self.model_dump_json(
            exclude_none=True,
            exclude=self._exclude_from_base_state,
        )
        fs.write(BASE_STATE, payload)

    @classmethod
    def load(
        cls: type["ConversationState"], file_store: FileStore
    ) -> "ConversationState":
        """Load ConversationState from persist_dir (base snapshot + replay manifest)."""
        manifest = Manifest.read(file_store)

        # Fresh init if both missing
        if not (txt := _read_text(file_store, BASE_STATE)) and not manifest.segments:
            state = cls()
            state._save_base_state(file_store)
            manifest.write(file_store)
            return state

        assert isinstance(txt, str)
        base_dict = json.loads(txt)
        state = cls.model_validate(base_dict)
        manifest.reconcile_with_fs(file_store)
        for ev in manifest.replay(file_store):
            state.events.append(ev)
        return state

    def save(self, file_store: FileStore) -> None:
        """Persist current state (update base, append deltas,
        compact opportunistically).
        """
        manifest = Manifest.read(file_store)

        # keep base snapshot current (crash-safe)
        self._save_base_state(file_store)

        # reconcile, then append any missing events
        manifest.reconcile_with_fs(file_store)
        next_idx = manifest.next_event_index()
        if next_idx < len(self.events):
            for idx in range(next_idx, len(self.events)):
                manifest.append_delta(
                    file_store, idx, self.events[idx], flush_manifest=True
                )

        # opportunistic compaction
        if manifest.compact(file_store, shard_size=SHARD_SIZE):
            manifest.write(file_store)
