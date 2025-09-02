import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError


if TYPE_CHECKING:
    from .conversation import Conversation  # noqa

from openhands.core.io import FileStore, LocalFileStore
from openhands.core.logger import get_logger


logger = get_logger(__name__)


INDEX_WIDTH = 4
MESSAGE_DIR_NAME = "messages"
BASE_STATE_NAME = "base_state.json"

class ConversationPersistence:
    """
    Layout under `root/`:
      - base_state.json                     # small JSON
      - messages/<index>-<ts>.jsonl         # one message per file, one JSON object per line

    Conventions:
      - <index> is zero-padded to `cfg.index_width`
      - <ts> is UTC: YYYYMMDDTHHMMSS
    """

    _RE_INDIV = re.compile(
        r"^(?P<idx>\d+)-(?P<ts>\d{8}T\d{6})\.jsonl$"
    )

    # ---------- Public API ----------

    def save(self, obj: "Conversation", dir_path: str, filestore: FileStore | None = None) -> None:
        """
        Persist `obj.state` into `dir_path`:
          - overwrite base_state.json each call (it’s small)
          - enumerate existing message files to see which indices are already saved
          - write new files for missing indices
        """
        filestore = filestore or LocalFileStore(root=dir_path)
        # Use keys relative to the filestore root
        base_path = BASE_STATE_NAME
        msg_dir = MESSAGE_DIR_NAME

        with obj.state:
            # 1) write base_state (without messages)
            self._write_base_state(base_path, obj, filestore)

            # 2) compute which indices are already on disk
            saved_indices = self._saved_indices(msg_dir, filestore)

            # 3) write missing messages
            msgs = obj.state.history.messages
            for idx, msg in enumerate(msgs):
                if idx in saved_indices:
                    continue
                self._write_individual(msg_dir, idx, msg, filestore)

    def load(self, cls: "type[Conversation]", agent, dir_path: str, ConversationState, Message, file_store: FileStore | None = None, **kwargs) -> "Conversation":
        """
        Restore a Conversation instance from `dir_path`:
          - read base_state.json
          - list and sort individual message files
          - stream JSONL and validate into Message objects
        """
        filestore = file_store or LocalFileStore(root=dir_path)
        base_path = BASE_STATE_NAME

        base_state_dict = json.loads(filestore.read(base_path))

        obj: "Conversation" = cls(agent=agent, **kwargs)
        with obj.state:
            obj.state = ConversationState.model_validate(base_state_dict)

            msg_dir = MESSAGE_DIR_NAME
            # collect (idx, path) for individual files
            entries: list[tuple[int, str]] = []
            for p in filestore.list(msg_dir):
                name = os.path.basename(p)
                m = self._RE_INDIV.match(name)
                if m:
                    entries.append((int(m.group("idx")), p))
            entries.sort(key=lambda t: t[0])

            # append messages in order
            for _, path in entries:
                blob = filestore.read(path)
                for line in blob.splitlines():
                    if not line:
                        continue
                    msg_dict = json.loads(line)
                    try:
                        obj.state.history.messages.append(
                            Message.model_validate(msg_dict)
                        )
                    except ValidationError as e:
                        logger.error(f"Failed to validate message from {path}: {e}")
        return obj

    # ---------- Internals ----------

    def _write_base_state(self, base_path: str, obj: "Conversation", file_store: FileStore, ) -> None:
        base = obj.state.model_copy()
        base.history = type(obj.state.history)()  # empty history
        data = json.dumps(base.model_dump(), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        file_store.write(base_path, data)

    def _write_individual(self, msg_dir: str, index: int, msg_model: Any, file_store: FileStore) -> None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        name = f"{index:0{INDEX_WIDTH}d}-{ts}.jsonl"
        path = self._join(msg_dir, name)
        line = (json.dumps(msg_model.model_dump(), ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        file_store.write(path, line)

    def _saved_indices(self, msg_dir: str, file_store: FileStore) -> set[int]:
        saved: set[int] = set()
        for p in file_store.list(msg_dir):
            name = os.path.basename(p)
            m = self._RE_INDIV.match(name)
            if m:
                saved.add(int(m.group("idx")))
        return saved

    @staticmethod
    def _join(prefix: str, *parts: str) -> str:
        return str(Path(prefix).joinpath(*parts))
