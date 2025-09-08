# persistence.py
import json
import re
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from openhands.sdk.event import Event, EventBase
from openhands.sdk.io import FileStore
from openhands.sdk.logger import get_logger


logger = get_logger(__name__)

# -------- constants --------
BASE_STATE = "base_state.json"
MANIFEST = "manifest.json"
EVENTS_DIR = "events"
SHARD_SIZE = 20  # compact after this many trailing deltas

# -------- fs helpers (FileStore.read returns str) --------


def _read_text(fs: FileStore, path: str) -> Optional[str]:
    try:
        return fs.read(path)  # str
    except Exception:
        logger.warning(f"Failed to read {path} from filestore", exc_info=True)
        return None


def _write_text(fs: FileStore, path: str, text: str) -> None:
    fs.write(path, text)


# -------- segments (Pydantic) --------
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

# -------- Manifest (Pydantic) --------
_DELTA_NAME_RE = re.compile(r"^delta-(?P<idx>\d{6})-\d{8}T\d{6}\.json$")


class Manifest(BaseModel):
    segments: list[Segment] = Field(default_factory=list)

    # ---- index helpers ----
    def next_event_index(self) -> int:
        if not self.segments:
            return 0
        last = -1
        for s in self.segments:
            if isinstance(s, DeltaSeg):
                last = max(last, s.index)
            else:
                last = max(last, s.start + s.count - 1)
        return last + 1

    def next_part_number(self) -> int:
        n = -1
        for s in self.segments:
            if isinstance(s, PartSeg):
                fname = s.file.rsplit("/", 1)[-1]
                try:
                    n = max(n, int(fname.split("-")[1].split(".")[0]))
                except Exception:
                    n = max(n, 0)
        return n + 1

    # ---- manifest IO ----
    @classmethod
    def read(cls, fs: FileStore, path: str = MANIFEST) -> "Manifest":
        txt = _read_text(fs, path)
        if not txt:
            return cls()
        try:
            data = json.loads(txt)
            return cls.model_validate({"segments": data})
        except Exception:
            return cls()

    def write(self, fs: FileStore, path: str = MANIFEST) -> None:
        payload = [s.model_dump(exclude_none=True) for s in self.segments]
        _write_text(fs, path, json.dumps(payload))

    # ---- discovery/recovery ----
    def _list_delta_files(self, fs: FileStore) -> list[tuple[int, str]]:
        """List delta files in EVENTS_DIR, returning (index, path)
        tuples sorted by index.
        """
        try:
            paths = fs.list(EVENTS_DIR)
        except Exception:
            return []
        out: list[tuple[int, str]] = []
        for p in paths:
            name = p.rsplit("/", 1)[-1]
            m = _DELTA_NAME_RE.match(name)
            if m:
                out.append((int(m.group("idx")), p))
        out.sort(key=lambda t: t[0])
        return out

    def reconcile_with_fs(self, fs: FileStore) -> bool:
        """Reconcile manifest with files in EVENTS_DIR.

        Returns True if manifest changed and should be written.
        """
        known = {s.index for s in self.segments if isinstance(s, DeltaSeg)}
        changed = False
        for idx, path in self._list_delta_files(fs):
            if idx not in known:
                self.segments.append(DeltaSeg(file=path, index=idx))
                changed = True
        if changed:
            self.write(fs)
        return changed

    # ---- event ops ----
    def append_delta(
        self, fs: FileStore, idx: int, event: Event, flush_manifest: bool = True
    ) -> None:
        """Append a new delta event, optionally flushing the manifest."""
        ts_utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        path = f"{EVENTS_DIR}/delta-{idx:06d}-{ts_utc}.json"
        _write_text(fs, path, event.model_dump_json(exclude_none=True))
        self.segments.append(DeltaSeg(file=path, index=idx))
        if flush_manifest:
            self.write(fs)

    def replay(self, fs: FileStore) -> list[Event]:
        """Replay all events in order."""
        out: list[Event] = []
        for seg in self.segments:
            txt = _read_text(fs, seg.file)
            if not txt:
                continue
            if isinstance(seg, DeltaSeg):
                out.append(EventBase.model_validate(json.loads(txt)))
            else:
                for line in txt.splitlines():
                    if line:
                        out.append(EventBase.model_validate(json.loads(line)))
        return out

    # ---- compaction ----
    def compact(self, fs: FileStore, shard_size: int = SHARD_SIZE) -> bool:
        i = 0
        changed = False
        while i < len(self.segments):
            if not isinstance(self.segments[i], DeltaSeg):
                i += 1
                continue

            j = i
            while j < len(self.segments) and isinstance(self.segments[j], DeltaSeg):
                j += 1

            assert all(isinstance(s, DeltaSeg) for s in self.segments[i:j])
            run: list[DeltaSeg] = [s for s in self.segments[i:j]]  # type: ignore
            if len(run) < shard_size:
                i = j
                continue

            full_chunks = len(run) // shard_size
            replacement: list[Segment] = []
            for c in range(full_chunks):
                chunk = run[c * shard_size : (c + 1) * shard_size]
                chunk.sort(key=lambda s: s.index)
                start_idx = chunk[0].index

                events_json: list[dict[str, Any]] = []
                for s in chunk:
                    txt = _read_text(fs, s.file)
                    if txt:
                        events_json.append(json.loads(txt))

                part_no = self.next_part_number()
                part_path = f"{EVENTS_DIR}/part-{part_no:06d}.jsonl"
                _write_text(
                    fs,
                    part_path,
                    "".join(
                        json.dumps(e, separators=(",", ":")) + "\n" for e in events_json
                    ),
                )
                replacement.append(
                    PartSeg(file=part_path, start=start_idx, count=len(events_json))
                )

            leftover = run[full_chunks * shard_size :]
            replacement.extend(leftover)

            self.segments[i:j] = replacement
            changed = True
            i += len(replacement)

        return changed
