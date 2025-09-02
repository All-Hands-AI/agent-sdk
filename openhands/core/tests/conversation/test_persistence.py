import os
from pathlib import Path
from typing import Any, cast

from openhands.core.agent.base import AgentBase
from openhands.core.conversation import Conversation
from openhands.core.conversation.persistence import BASE_STATE_NAME, MESSAGE_DIR_NAME
from openhands.core.conversation.state import ConversationState
from openhands.core.io.local import LocalFileStore
from openhands.core.llm import Message, TextContent
from openhands.core.tool import Tool


class DummyAgent(AgentBase):
    """Minimal agent that just records the initial user message."""

    def __init__(self) -> None:
        super().__init__(llm=cast(Any, object()), tools=cast(list[Tool], []))

    def init_state(
        self,
        state: ConversationState,
        initial_user_message: Message | None = None,
        on_event=None,
    ) -> None:
        if initial_user_message is not None:
            state.history.messages.append(initial_user_message)
            state.agent_initialized = True
            if on_event:
                on_event(initial_user_message)

    def step(self, state: ConversationState, on_event=None) -> None:  # pragma: no cover - not used in these tests
        state.agent_finished = True


def _physical_path(root: Path, rel: str) -> Path:
    """Replicate LocalFileStore path resolution so tests can inspect files on disk."""
    fs = LocalFileStore(str(root))
    # LocalFileStore.get_full_path expects a string path relative to the filestore root
    return Path(fs.get_full_path(rel))


def test_save_no_messages_writes_base_state_only(tmp_path: Path) -> None:
    conv = Conversation(agent=DummyAgent())

    # Save immediately (no messages)
    conv.save(str(tmp_path))

    base_rel = BASE_STATE_NAME
    msg_dir_rel = MESSAGE_DIR_NAME

    base_path = _physical_path(tmp_path, base_rel)
    msg_dir_path = _physical_path(tmp_path, msg_dir_rel)

    assert base_path.exists(), "base_state.json should be written"
    assert not msg_dir_path.exists(), "messages directory should not exist when no messages"


def test_save_then_resave_no_duplicate_messages(tmp_path: Path) -> None:
    conv = Conversation(agent=DummyAgent())
    conv.send_message(Message(role="user", content=[TextContent(text="hi")]))

    conv.save(str(tmp_path))

    msg_dir_rel = MESSAGE_DIR_NAME
    msg_dir_path = _physical_path(tmp_path, msg_dir_rel)
    assert msg_dir_path.exists()

    files1 = sorted(os.listdir(msg_dir_path))
    assert len(files1) == 1 and files1[0].startswith("0000-"), files1

    # Save again without changes: should not create a new file
    conv.save(str(tmp_path))

    files2 = sorted(os.listdir(msg_dir_path))
    assert files2 == files1, "Saving twice without changes should not duplicate message files"


def test_incremental_save_writes_only_new_indices(tmp_path: Path) -> None:
    conv = Conversation(agent=DummyAgent())
    conv.send_message(Message(role="user", content=[TextContent(text="hi")]))
    conv.save(str(tmp_path))

    msg_dir_rel = MESSAGE_DIR_NAME
    msg_dir_path = _physical_path(tmp_path, msg_dir_rel)

    files1 = sorted(os.listdir(msg_dir_path))
    assert len(files1) == 1 and files1[0].startswith("0000-"), files1

    # Add second message and save again; only index 0001 should be new
    conv.send_message(Message(role="user", content=[TextContent(text="second")]))
    conv.save(str(tmp_path))

    files2 = sorted(os.listdir(msg_dir_path))
    assert len(files2) == 2
    assert files2[0].startswith("0000-") and files2[1].startswith("0001-")


def test_saved_indices_ignores_invalid_filenames(tmp_path: Path) -> None:
    conv = Conversation(agent=DummyAgent())

    # Place a junk file in messages dir that shouldn't match the regex
    junk_rel_dir = MESSAGE_DIR_NAME
    junk_dir = _physical_path(tmp_path, junk_rel_dir)
    junk_dir.mkdir(parents=True, exist_ok=True)
    (junk_dir / "not-a-message.txt").write_text("junk")

    # First real message should still be written as 0000-*.jsonl
    conv.send_message(Message(role="user", content=[TextContent(text="hi")]))
    conv.save(str(tmp_path))

    files = sorted(os.listdir(junk_dir))
    assert any(f.startswith("0000-") and f.endswith(".jsonl") for f in files), files
