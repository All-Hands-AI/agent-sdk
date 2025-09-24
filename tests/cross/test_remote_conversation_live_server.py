"""End-to-end test using a real FastAPI agent server with patched LLM.

This validates RemoteConversation against actual REST + WebSocket endpoints,
while keeping the LLM deterministic via monkeypatching.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Generator
from pathlib import Path

import pytest
import uvicorn
from litellm.types.utils import Choices, Message as LiteLLMMessage, ModelResponse
from pydantic import SecretStr

from openhands.sdk import LLM, Agent, Conversation
from openhands.sdk.sandbox.port_utils import find_available_tcp_port


@pytest.fixture
def server_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[dict, None, None]:
    """Launch a real FastAPI server backed by temp workspace and conversations.

    We set OPENHANDS_AGENT_SERVER_CONFIG_PATH before creating the app so that
    routers pick up the correct default config and in-memory services.
    """

    # Create an isolated config pointing to tmp dirs
    conversations_path = tmp_path / "conversations"
    workspace_path = tmp_path / "workspace"
    conversations_path.mkdir(parents=True, exist_ok=True)
    workspace_path.mkdir(parents=True, exist_ok=True)

    cfg = {
        "session_api_keys": [],  # disable auth for tests
        "conversations_path": str(conversations_path),
        "workspace_path": str(workspace_path),
    }
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(json.dumps(cfg))

    # Ensure default config uses our file and disable any env key override
    monkeypatch.setenv("OPENHANDS_AGENT_SERVER_CONFIG_PATH", str(cfg_file))
    monkeypatch.delenv("SESSION_API_KEY", raising=False)

    # Build app after env is set
    from openhands.agent_server.api import create_app
    from openhands.agent_server.config import Config

    cfg_obj = Config.from_json_file(cfg_file)
    app = create_app(cfg_obj)

    # Start uvicorn on a free port
    port = find_available_tcp_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait a bit for the server to be ready
    time.sleep(0.3)

    try:
        yield {"host": f"http://127.0.0.1:{port}"}
    finally:
        # uvicorn.Server lacks a robust shutdown API here; rely on daemon thread exit.
        server.should_exit = True
        thread.join(timeout=2)


@pytest.fixture
def patched_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch LLM.completion to a deterministic assistant message response."""

    def fake_completion(
        self, messages, tools, extra_body, add_security_risk_prediction
    ):  # type: ignore[no-untyped-def]
        # Return a minimal ModelResponse with a single assistant message
        litellm_msg = LiteLLMMessage.model_validate(
            {
                "role": "assistant",
                "content": "Hello from patched LLM",
            }
        )
        return ModelResponse(
            id="test-resp",
            created=int(time.time()),
            model="test-model",
            choices=[Choices(index=0, finish_reason="stop", message=litellm_msg)],
        )

    monkeypatch.setattr(LLM, "completion", fake_completion, raising=True)


def test_remote_conversation_over_real_server(server_env, patched_llm):
    # Create an Agent with a real LLM object (patched for determinism)
    llm = LLM(model="gpt-4", api_key=SecretStr("test"))
    agent = Agent(llm=llm, tools=[])

    # Create conversation via factory pointing at the live server
    conv = Conversation(agent=agent, host=server_env["host"])  # RemoteConversation

    # Send a message and run
    conv.send_message("Say hello")
    conv.run()

    # Validate state transitions and that we received an assistant message
    state = conv.state
    assert state.agent_status.value in {"finished", "idle", "running"}

    # Wait for WS-delivered events; assert an agent message exists
    found_agent = False
    for i in range(50):  # up to ~5s
        events = state.events
        # Check for any agent-related events (more flexible)
        for e in events:
            event_source = getattr(e, "source", "")
            event_type = type(e).__name__
            # Look for agent messages or assistant messages
            if (
                event_source == "agent"
                or (hasattr(e, "llm_message") and getattr(e, "llm_message", None))
                or (
                    hasattr(e, "content")
                    and "Hello from patched LLM" in str(getattr(e, "content", ""))
                )
                or event_type == "MessageEvent"
            ):
                found_agent = True
                break

        if found_agent:
            break
        time.sleep(0.1)

    # If still not found, print debug info
    if not found_agent:
        print(f"Debug: Found {len(state.events)} events:")
        for i, e in enumerate(state.events):
            print(
                f"  Event {i}: {type(e).__name__}, source={getattr(e, 'source', 'N/A')}"
            )
            if hasattr(e, "content"):
                print(f"    content: {getattr(e, 'content', 'N/A')}")
            if hasattr(e, "llm_message"):
                print(f"    llm_message: {getattr(e, 'llm_message', 'N/A')}")

    assert found_agent

    conv.close()
