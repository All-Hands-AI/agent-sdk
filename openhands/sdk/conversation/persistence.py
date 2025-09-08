# persistence_helpers.py
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import List, Literal

from pydantic import BaseModel, Field, ValidationError

from openhands.sdk.conversation.state import ConversationState
from openhands.sdk.event import Event, EventBase
from openhands.sdk.io import FileStore


BASE_STATE = "base_state.json"
MANIFEST = "manifest.json"
EVENTS_DIR = "events"
SHARD_SIZE = 20  # compact after this many trailing deltas


# ---------- Pydantic models ----------


class DeltaSeg(BaseModel):
    type: Literal["delta"] = "delta"
    file: str
    index: int = Field(ge=0)


class PartSeg(BaseModel):
    type: Literal["part"] = "part"
    file: str
    start: int = Field(ge=0)
    count: int = Field(ge=1)


Segment = DeltaSeg | PartSeg


class Manifest(BaseModel):
    segments: List[Segment] = Field(default_factory=list)

    def next_event_index(self) -> int:
        if not self.segments:
            return 0
        last = -1
        for s in self.segments:
            if isinstance(s, DeltaSeg):
                if s.index > last:
                    last = s.index
            else:  # PartSeg
                assert isinstance(s, PartSeg)
                end = s.start + s.count - 1
                if end > last:
                    last = end
        return last + 1

    def next_part_number(self) -> int:
        n = -1
        for s in self.segments:
            if isinstance(s, PartSeg):
                try:
                    fname = s.file.rsplit("/", 1)[-1]
                    n = max(n, int(fname.split("-")[1].split(".")[0]))
                except Exception:
                    n = max(n, 0)
        return n + 1


# ---------- Tiny helper functions ----------


def write_base_state(fs: FileStore, state_model: ConversationState) -> None:
    """Persist ConversationState WITHOUT events (Pydantic model)."""
    base = state_model.model_copy()
    base.events = []
    fs.write(
        BASE_STATE,
        base.model_dump_json(exclude_none=True).encode("utf-8"),
    )


def read_manifest(fs: FileStore) -> Manifest:
    try:
        raw = fs.read(MANIFEST)
    except Exception:
        return Manifest()
    try:
        # fs.read may return bytes or str
        text = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw
        data = json.loads(text)
        return Manifest.model_validate({"segments": data})
    except (ValidationError, Exception):
        # If file existed but malformed, start fresh — simplest behavior.
        return Manifest()


def write_manifest(fs: FileStore, manifest: Manifest) -> None:
    # store as a *list* (not an object) for easy inspection
    payload = [s.model_dump(exclude_none=True) for s in manifest.segments]
    fs.write(MANIFEST, json.dumps(payload, separators=(",", ":")).encode("utf-8"))


def append_delta(
    fs: FileStore,
    manifest: Manifest,
    idx: int,
    event: Event,
    flush_manifest: bool = True,
) -> None:
    """Per-event durability: write object first, then record it in manifest."""
    ts_utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    delta_path = f"{EVENTS_DIR}/delta-{idx:06d}-{ts_utc}.json"
    fs.write(
        delta_path,
        event.model_dump_json(exclude_none=True).encode("utf-8"),
    )
    manifest.segments.append(DeltaSeg(file=delta_path, index=idx))
    if flush_manifest:
        write_manifest(fs, manifest)


def compact_tail(
    fs: FileStore, manifest: Manifest, shard_size: int = SHARD_SIZE
) -> bool:
    """
    If there are >= shard_size trailing deltas, replace them with one 'part' entry.
    Returns True if a compaction happened.
    """
    # collect trailing deltas
    tail: List[DeltaSeg] = []
    for s in reversed(manifest.segments):
        if not isinstance(s, DeltaSeg):
            break
        tail.append(s)
        if len(tail) >= shard_size:
            break
    if len(tail) < shard_size:
        return False

    # oldest → newest
    tail.sort(key=lambda s: s.index)
    start = tail[0].index

    # read events for the tail
    events_json = []
    for s in tail:
        blob = fs.read(s.file)
        text = blob.decode("utf-8") if isinstance(blob, (bytes, bytearray)) else blob
        events_json.append(json.loads(text))

    # write part file
    part_no = manifest.next_part_number()
    part_path = f"{EVENTS_DIR}/part-{part_no:06d}.jsonl"
    fs.write(
        part_path,
        b"".join(
            (json.dumps(e, separators=(",", ":")) + "\n").encode("utf-8")
            for e in events_json
        ),
    )

    # replace tail deltas with single part segment
    # (pop from end; we know tail are the last len(tail) entries)
    for _ in range(len(tail)):
        manifest.segments.pop()
    manifest.segments.append(
        PartSeg(file=part_path, start=start, count=len(events_json))
    )

    return True


def replay_manifest(fs: FileStore, manifest: Manifest) -> List[Event]:
    """Materialize events in strict manifest order using Pydantic validation."""
    out: List[Event] = []
    for seg in manifest.segments:
        if isinstance(seg, DeltaSeg):
            blob = fs.read(seg.file)
            text = (
                blob.decode("utf-8") if isinstance(blob, (bytes, bytearray)) else blob
            )
            out.append(EventBase.model_validate(json.loads(text)))
        else:  # PartSeg
            blob = fs.read(seg.file)
            text = (
                blob.decode("utf-8") if isinstance(blob, (bytes, bytearray)) else blob
            )
            for line in text.splitlines():
                if not line:
                    continue
                out.append(EventBase.model_validate(json.loads(line)))
    return out
