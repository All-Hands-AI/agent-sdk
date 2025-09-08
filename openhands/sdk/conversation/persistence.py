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


def compact_runs(
    fs: FileStore, manifest: Manifest, shard_size: int = SHARD_SIZE
) -> bool:
    """
    Left-to-right compaction:
      - Find each contiguous run of DeltaSeg.
      - From the *front* of the run, chunk by shard_size.
      - Replace each full chunk with a PartSeg.
      - Leave a remainder (< shard_size) as trailing deltas.
    Returns True if any compaction happened.
    """
    i = 0
    changed = False
    while i < len(manifest.segments):
        # Skip non-delta segments
        if not isinstance(manifest.segments[i], DeltaSeg):
            i += 1
            continue

        # Identify contiguous run [i, j) of DeltaSeg
        j = i
        while j < len(manifest.segments) and isinstance(manifest.segments[j], DeltaSeg):
            j += 1

        run: list[DeltaSeg] = [
            s for s in manifest.segments[i:j] if isinstance(s, DeltaSeg)
        ]
        run_len = len(run)
        if run_len >= shard_size:
            # Number of full chunks we can compact from the *front* of the run
            full_chunks = run_len // shard_size
            # We'll build a replacement list for [i, j)
            replacement: list[Segment] = []
            # Process full chunks
            for c in range(full_chunks):
                chunk = run[c * shard_size : (c + 1) * shard_size]
                # Oldest → newest by index
                chunk.sort(key=lambda s: s.index)
                start_idx = chunk[0].index

                # Read events
                events_json = []
                for s in chunk:
                    blob = fs.read(s.file)
                    text = (
                        blob.decode("utf-8")
                        if isinstance(blob, (bytes, bytearray))
                        else blob
                    )
                    events_json.append(json.loads(text))

                # Write part
                part_no = manifest.next_part_number()
                part_path = f"{EVENTS_DIR}/part-{part_no:06d}.jsonl"
                fs.write(
                    part_path,
                    b"".join(
                        [
                            (json.dumps(e, separators=(",", ":")) + "\n").encode(
                                "utf-8"
                            )
                            for e in events_json
                        ]
                    ),
                )

                replacement.append(
                    PartSeg(file=part_path, start=start_idx, count=len(events_json))
                )

            # Append leftover (< shard_size) deltas unchanged
            leftover = run[full_chunks * shard_size :]
            replacement.extend(leftover)

            # Splice replacement back into manifest
            manifest.segments[i:j] = replacement
            changed = True
            # Advance i to after the replacement we just inserted
            i = i + len(replacement)
        else:
            # Run too small to compact, skip past it
            i = j

    return changed


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
