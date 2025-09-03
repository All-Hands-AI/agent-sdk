import os
from pathlib import Path
from typing import Any, cast

from openhands.sdk.agent.base import AgentBase
from openhands.sdk.conversation import Conversation
from openhands.sdk.conversation.persistence import (
    BASE_STATE_NAME,
    EVENTS_DIR_NAME,
    MESSAGE_DIR_NAME,
)
from openhands.sdk.conversation.state import ConversationState
from openhands.sdk.event import MessageEvent
from openhands.sdk.io.local import LocalFileStore
from openhands.sdk.llm import Message, TextContent
from openhands.sdk.tool import Tool


class DummyAgent(AgentBase):
    """Minimal agent used for persistence tests."""

    def __init__(self) -> None:
        super().__init__(llm=cast(Any, object()), tools=cast(list[Tool], []))

    def init_state(
        self,
        state: ConversationState,
        on_event,
    ) -> None:
        # No-op for these tests
        pass

    def step(
        self, state: ConversationState, on_event
    ) -> None:  # pragma: no cover - not used in these tests
        state.agent_finished = True


def _physical_path(root: Path, rel: str) -> Path:
    """Resolve a filestore-relative key to a physical path under tmp root."""
    fs = LocalFileStore(str(root))
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
    assert not msg_dir_path.exists(), (
        "messages directory should not exist when no messages"
    )


def test_save_then_resave_no_duplicate_events(tmp_path: Path) -> None:
    conv = Conversation(agent=DummyAgent())
    conv.send_message(Message(role="user", content=[TextContent(text="hi")]))

    conv.save(str(tmp_path))

    events_dir_rel = EVENTS_DIR_NAME
    events_dir_path = _physical_path(tmp_path, events_dir_rel)
    assert events_dir_path.exists()

    files1 = sorted(os.listdir(events_dir_path))
    assert len(files1) == 1 and files1[0].startswith("0000-"), files1

    # Save again without changes: should not create a new file
    conv.save(str(tmp_path))

    files2 = sorted(os.listdir(events_dir_path))
    assert files2 == files1, (
        "Saving twice without changes should not duplicate event files"
    )


def test_incremental_save_writes_only_new_indices(tmp_path: Path) -> None:
    conv = Conversation(agent=DummyAgent())
    conv.send_message(Message(role="user", content=[TextContent(text="hi")]))
    conv.save(str(tmp_path))

    events_dir_rel = EVENTS_DIR_NAME
    events_dir_path = _physical_path(tmp_path, events_dir_rel)

    files1 = sorted(os.listdir(events_dir_path))
    assert len(files1) == 1 and files1[0].startswith("0000-"), files1

    # Add second message and save again; only index 0001 should be new
    conv.send_message(Message(role="user", content=[TextContent(text="second")]))
    conv.save(str(tmp_path))

    files2 = sorted(os.listdir(events_dir_path))
    assert len(files2) == 2
    assert files2[0].startswith("0000-") and files2[1].startswith("0001-")


def test_saved_indices_ignores_invalid_filenames(tmp_path: Path) -> None:
    conv = Conversation(agent=DummyAgent())

    # Place a junk file in events dir that shouldn't match the regex
    junk_rel_dir = EVENTS_DIR_NAME
    junk_dir = _physical_path(tmp_path, junk_rel_dir)
    junk_dir.mkdir(parents=True, exist_ok=True)
    (junk_dir / "not-an-event.txt").write_text("junk")

    # First real event should still be written as 0000-*.jsonl
    conv.send_message(Message(role="user", content=[TextContent(text="hi")]))
    conv.save(str(tmp_path))

    files = sorted(os.listdir(junk_dir))
    assert any(f.startswith("0000-") and f.endswith(".jsonl") for f in files), files


def test_save_creates_events_directory(tmp_path: Path) -> None:
    """Test that events directory is created and ALL events are saved."""
    conv = Conversation(agent=DummyAgent())

    # Add a regular message (LLMConvertibleEvent)
    conv.send_message(Message(role="user", content=[TextContent(text="hi")]))

    # Save the conversation
    conv.save(str(tmp_path))

    # Check that events directory exists and contains files
    events_dir_path = _physical_path(tmp_path, EVENTS_DIR_NAME)
    assert events_dir_path.exists(), "events directory should exist"

    events_files = sorted(os.listdir(events_dir_path))
    assert len(events_files) == 1, (
        f"Should have 1 event file, got {len(events_files)}: {events_files}"
    )
    assert events_files[0].startswith("0000-") and events_files[0].endswith(".jsonl")

    # Check that messages directory does NOT exist (no longer created)
    msg_dir_path = _physical_path(tmp_path, MESSAGE_DIR_NAME)
    assert not msg_dir_path.exists(), "messages directory should not be created anymore"


def test_load_prioritizes_events_over_messages(tmp_path: Path) -> None:
    """Test that loading prioritizes events directory over messages directory."""
    conv = Conversation(agent=DummyAgent())
    conv.send_message(Message(role="user", content=[TextContent(text="test message")]))

    # Save the conversation (creates both events and messages directories)
    conv.save(str(tmp_path))

    # Load the conversation back
    loaded_conv = Conversation.load(str(tmp_path), agent=DummyAgent())

    # Should have loaded from events directory
    assert len(loaded_conv.state.events) == 1
    assert isinstance(loaded_conv.state.events[0], MessageEvent)
    # Check the message content properly
    content = loaded_conv.state.events[0].llm_message.content[0]
    assert isinstance(content, TextContent) and content.text == "test message"
