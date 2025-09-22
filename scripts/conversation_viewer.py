"""Streamlit app to explore OpenHands conversation logs.

Usage:
    streamlit run examples/conversation_viewer.py

The viewer expects a directory containing conversation folders. By default we
look for ``.conversations`` next to the repository root (the location created by
``openhands`` when recording sessions). You can override the location via:

* Environment variable ``OPENHANDS_CONVERSATIONS_ROOT``
* URL query parameter ``?root=/path/to/logs`` when the app is open
* The sidebar text input labelled "Conversations directory"

Each conversation directory should contain ``base_state.json`` plus an
``events/`` folder with individual ``*.json`` event files. The viewer will
summarise events in a table and show their full payload when expanded.
"""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import streamlit as st


ENV_ROOT = os.getenv("OPENHANDS_CONVERSATIONS_ROOT")
DEFAULT_CONVERSATIONS_ROOT = (
    Path(ENV_ROOT).expanduser()
    if ENV_ROOT
    else Path(__file__).resolve().parents[1] / ".conversations"
)

st.set_page_config(page_title="OpenHands Agent-SDK Conversation Viewer", layout="wide")


@dataclass
class Conversation:
    identifier: str
    path: Path
    base_state: dict[str, Any]
    events: list[dict[str, Any]]


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def add_filename(event: dict[str, Any], filename: str) -> dict[str, Any]:
    event_copy = dict(event)
    event_copy["_filename"] = filename
    return event_copy


@st.cache_data(show_spinner=False)
def load_conversation(path_str: str) -> Conversation:
    path = Path(path_str)
    identifier = path.name

    base_state: dict[str, Any] = {}
    base_state_path = path / "base_state.json"
    if base_state_path.exists():
        try:
            base_state = load_json(base_state_path)
        except json.JSONDecodeError as exc:
            base_state = {"error": f"Failed to parse base_state.json: {exc}"}

    events_dir = path / "events"
    events: list[dict[str, Any]] = []
    if events_dir.exists():
        for event_file in sorted(events_dir.glob("*.json")):
            try:
                event_data = load_json(event_file)
                events.append(add_filename(event_data, event_file.name))
            except json.JSONDecodeError as exc:
                events.append(
                    {
                        "kind": "InvalidJSON",
                        "source": "parser",
                        "timestamp": "",
                        "error": str(exc),
                        "_filename": event_file.name,
                    }
                )

    return Conversation(
        identifier=identifier, path=path, base_state=base_state, events=events
    )


def conversation_dirs(root: Path) -> list[Path]:
    """Return sorted conversation sub-directories under ``root``."""
    return sorted((p for p in root.iterdir() if p.is_dir()), key=lambda item: item.name)


def extract_text_blocks(blocks: Iterable[Any] | None) -> str:
    pieces: list[str] = []
    for block in blocks or []:
        if isinstance(block, dict):
            block_type = block.get("type")
            if block_type == "text":
                pieces.append(str(block.get("text", "")))
            elif "text" in block:
                pieces.append(str(block.get("text")))
            elif "content" in block:
                pieces.append(extract_text_blocks(block.get("content")))
        elif isinstance(block, str):
            pieces.append(block)
    return "\n".join(piece for piece in pieces if piece)


def get_event_text(event: dict[str, Any]) -> str:
    kind = event.get("kind")
    if kind == "MessageEvent":
        message = event.get("llm_message", {})
        return extract_text_blocks(message.get("content", []))
    if kind == "ActionEvent":
        segments: list[str] = []
        segments.append(extract_text_blocks(event.get("thought", [])))
        action = event.get("action", {})
        if isinstance(action, dict):
            if action.get("command"):
                segments.append(str(action.get("command")))
            if action.get("path"):
                segments.append(f"Path: {action.get('path')}")
            if action.get("file_text"):
                segments.append(action.get("file_text", ""))
        return "\n\n".join(s for s in segments if s)
    if kind == "ObservationEvent":
        observation = event.get("observation", {})
        return extract_text_blocks(observation.get("content", []))
    if kind == "SystemPromptEvent":
        prompt = event.get("system_prompt", {})
        if isinstance(prompt, dict) and prompt.get("type") == "text":
            return str(prompt.get("text", ""))
    return ""


def truncate(text: str, limit: int = 160) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1] + "\u2026"


def event_summary_rows(events: Sequence[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for idx, event in enumerate(events):
        kind = event.get("kind", "")
        source = event.get("source", "")
        preview = (
            truncate(get_event_text(event))
            if kind != "InvalidJSON"
            else event.get("error", "")
        )
        rows.append(
            {
                "#": f"{idx:03d}",
                "File": event.get("_filename", ""),
                "Kind": kind,
                "Source": source,
                "Timestamp": event.get("timestamp", ""),
                "Preview": preview,
            }
        )
    return rows


def draw_base_state(base_state: dict[str, Any]) -> None:
    if not base_state:
        st.info("No base_state.json found for this conversation.")
        return

    st.subheader("Base State")
    cols = st.columns(3)
    agent = base_state.get("agent", {})
    llm = agent.get("llm", {})
    cols[0].metric("Agent kind", agent.get("kind", "Unknown"))
    cols[1].metric("LLM model", llm.get("model", "Unknown"))
    cols[2].metric("Temperature", str(llm.get("temperature", "Unknown")))

    with st.expander("View raw base_state.json", expanded=False):
        st.json(base_state)


def draw_event_detail(event: dict[str, Any]) -> None:
    meta_cols = st.columns(4)
    meta_cols[0].markdown(f"**File**\n{event.get('_filename', '—')}")
    meta_cols[1].markdown(f"**Kind**\n{event.get('kind', '—')}")
    meta_cols[2].markdown(f"**Source**\n{event.get('source', '—')}")
    meta_cols[3].markdown(f"**Timestamp**\n{event.get('timestamp', '—')}")

    text = get_event_text(event)
    if text:
        st.markdown("**Narrative**")
        st.code(text)

    if event.get("kind") == "ActionEvent" and event.get("action"):
        st.markdown("**Action Payload**")
        st.json(event.get("action"))

    if event.get("kind") == "ObservationEvent" and event.get("observation"):
        st.markdown("**Observation Payload**")
        st.json(event.get("observation"))

    st.markdown("**Raw Event JSON**")
    st.json(event)


def main() -> None:
    st.title("OpenHands Conversation Viewer")

    params = st.query_params
    default_root = DEFAULT_CONVERSATIONS_ROOT
    initial_root = params.get("root", [str(default_root)])[0]

    root_input = st.sidebar.text_input(
        "Conversations directory",
        value=initial_root,
        help="Root folder containing OpenHands conversation dumps",
    )
    root_path = Path(root_input).expanduser()

    if root_input != params.get("root", [None])[0] and not st.session_state.get(
        "_suppress_query_update", False
    ):
        try:
            st.session_state["_suppress_query_update"] = True
            st.query_params["root"] = root_input
        finally:
            st.session_state["_suppress_query_update"] = False

    if st.sidebar.button(
        "Reload conversations", help="Clear cached data and reload from disk"
    ):
        load_conversation.clear()
        rerun = getattr(st, "experimental_rerun", None)
        if callable(rerun):
            rerun()
        else:
            st.rerun()

    if not root_path.exists() or not root_path.is_dir():
        st.error(f"Directory not found: {root_path}")
        return

    directories = conversation_dirs(root_path)
    if not directories:
        st.warning("No conversation folders found in the selected directory.")
        return

    options = [directory.name for directory in directories]
    selected_idx = 0
    if "conversation" in st.session_state:
        try:
            selected_idx = options.index(st.session_state["conversation"])
        except ValueError:
            selected_idx = 0

    selected = st.sidebar.selectbox("Conversation", options, index=selected_idx)
    st.session_state["conversation"] = selected

    conversation = load_conversation(str(root_path / selected))

    st.caption(f"Loaded from {conversation.path}")
    draw_base_state(conversation.base_state)

    st.subheader("Events")
    events = conversation.events
    if not events:
        st.info("No events found for this conversation.")
        return

    kinds = sorted({event.get("kind", "Unknown") for event in events})
    selected_kinds = st.sidebar.multiselect(
        "Filter by event kind", kinds, default=kinds
    )

    search_term = st.sidebar.text_input("Search across events", value="")
    lowered = search_term.lower()

    filtered_events: list[dict[str, Any]] = []
    for event in events:
        if selected_kinds and event.get("kind", "Unknown") not in selected_kinds:
            continue
        if lowered:
            as_text = json.dumps(event).lower()
            if lowered not in as_text:
                continue
        filtered_events.append(event)

    st.markdown(f"Showing {len(filtered_events)} of {len(events)} events")

    summary = event_summary_rows(filtered_events)
    st.dataframe(summary, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Event Details")

    for idx, event in enumerate(filtered_events):
        label = " · ".join(
            [
                f"{idx:03d}",
                event.get("kind", "Unknown"),
                event.get("source", "Unknown"),
            ]
        )
        with st.expander(label, expanded=False):
            draw_event_detail(event)


if __name__ == "__main__":
    main()
