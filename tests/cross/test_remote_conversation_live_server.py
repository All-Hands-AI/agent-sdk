"""End-to-end test using a real FastAPI agent server with patched LLM.

This validates RemoteConversation against actual REST + WebSocket endpoints,
while keeping the LLM deterministic via monkeypatching.
"""

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
from openhands.sdk.conversation import RemoteConversation
from openhands.sdk.event import (
    ActionEvent,
    AgentErrorEvent,
    CondensationSummaryEvent,
    ConversationStateUpdateEvent,
    Event,
    LLMConvertibleEvent,
    MessageEvent,
    ObservationEvent,
    PauseEvent,
    SystemPromptEvent,
)
from openhands.sdk.workspace import RemoteWorkspace
from openhands.workspace.docker.workspace import find_available_tcp_port


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

    # Ensure clean directories (both tmp and any leftover in cwd)
    import shutil
    from pathlib import Path

    # Clean up any leftover directories from previous runs in current working directory
    cwd_conversations = Path("workspace/conversations")
    if cwd_conversations.exists():
        shutil.rmtree(cwd_conversations)

    # Also clean up the workspace directory entirely to be safe
    cwd_workspace = Path("workspace")
    if cwd_workspace.exists():
        # Only remove conversations subdirectory to avoid interfering with other tests
        for item in cwd_workspace.iterdir():
            if item.name == "conversations":
                shutil.rmtree(item)

    # Clean up tmp directories
    if conversations_path.exists():
        shutil.rmtree(conversations_path)
    if workspace_path.exists():
        shutil.rmtree(workspace_path)

    conversations_path.mkdir(parents=True, exist_ok=True)
    workspace_path.mkdir(parents=True, exist_ok=True)

    # Verify the conversations directory is truly empty
    assert not list(conversations_path.iterdir()), (
        f"Conversations path not empty: {list(conversations_path.iterdir())}"
    )

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

    cfg_obj = Config.model_validate_json(cfg_file.read_text())

    app = create_app(cfg_obj)

    # Start uvicorn on a free port
    port = find_available_tcp_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait for the server to be ready with health check
    import httpx

    base_url = f"http://127.0.0.1:{port}"
    server_ready = False
    for attempt in range(50):  # Wait up to 5 seconds
        try:
            with httpx.Client() as client:
                response = client.get(f"{base_url}/health", timeout=2.0)
                if response.status_code == 200:
                    server_ready = True
                    break
        except (httpx.RequestError, httpx.TimeoutException):
            pass
        time.sleep(0.1)

    if not server_ready:
        raise RuntimeError("Server failed to start within timeout")

    try:
        yield {"host": f"http://127.0.0.1:{port}"}
    finally:
        # uvicorn.Server lacks a robust shutdown API here; rely on daemon thread exit.
        server.should_exit = True
        thread.join(timeout=2)

        # Clean up any leftover directories created during the test
        cwd_conversations = Path("workspace/conversations")
        if cwd_conversations.exists():
            shutil.rmtree(cwd_conversations)


@pytest.fixture
def patched_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch LLM.completion to a deterministic assistant message response."""

    def fake_completion(
        self,
        messages,
        tools,
        return_metrics=False,
        add_security_risk_prediction=False,
        **kwargs,
    ):  # type: ignore[no-untyped-def]
        from openhands.sdk.llm.llm_response import LLMResponse
        from openhands.sdk.llm.message import Message
        from openhands.sdk.llm.utils.metrics import MetricsSnapshot

        # Create a minimal ModelResponse with a single assistant message
        litellm_msg = LiteLLMMessage.model_validate(
            {
                "role": "assistant",
                "content": "Hello from patched LLM",
            }
        )
        raw_response = ModelResponse(
            id="test-resp",
            created=int(time.time()),
            model="test-model",
            choices=[Choices(index=0, finish_reason="stop", message=litellm_msg)],
        )

        # Convert to OpenHands Message
        message = Message.from_llm_chat_message(litellm_msg)

        # Create metrics snapshot
        metrics_snapshot = MetricsSnapshot(
            model_name="test-model",
            accumulated_cost=0.0,
            max_budget_per_task=None,
            accumulated_token_usage=None,
        )

        # Return LLMResponse as expected by the agent
        return LLMResponse(
            message=message, metrics=metrics_snapshot, raw_response=raw_response
        )

    monkeypatch.setattr(LLM, "completion", fake_completion, raising=True)


def test_remote_conversation_over_real_server(server_env, patched_llm):
    import shutil
    from pathlib import Path

    # Create an Agent with a real LLM object (patched for determinism)
    llm = LLM(model="gpt-4", api_key=SecretStr("test"))
    agent = Agent(llm=llm, tools=[])

    # Create conversation via factory pointing at the live server
    workspace = RemoteWorkspace(
        host=server_env["host"], working_dir="/tmp/workspace/project"
    )
    conv: RemoteConversation = Conversation(
        agent=agent, workspace=workspace
    )  # RemoteConversation

    # Send a message and run
    conv.send_message("Say hello")
    conv.run()

    # Validate state transitions and that we received an assistant message
    state = conv.state
    assert state.agent_status.value in {"finished", "idle", "running"}

    # Wait for WS-delivered events and validate them using proper type checking
    found_system_prompt = False
    found_state_update = False
    found_agent_related_event = False

    for i in range(50):  # up to ~5s
        events = state.events

        # Validate event types using isinstance checks (not hasattr/getattr)
        for e in events:
            assert isinstance(
                e,
                (
                    MessageEvent,
                    ActionEvent,
                    ObservationEvent,
                    AgentErrorEvent,
                    Event,
                    LLMConvertibleEvent,
                    SystemPromptEvent,
                    PauseEvent,
                    CondensationSummaryEvent,
                    ConversationStateUpdateEvent,
                ),
            ), f"Unexpected event type: {type(e).__name__}"

        # Check for expected event types with proper isinstance checks
        for e in events:
            if isinstance(e, SystemPromptEvent) and e.source == "agent":
                found_system_prompt = True
                # SystemPromptEvent is an agent-related event
                found_agent_related_event = True

            if isinstance(e, ConversationStateUpdateEvent):
                found_state_update = True
                # Verify it has the expected structure
                assert e.source == "environment", (
                    "ConversationStateUpdateEvent should have source='environment'"
                )

            # Check for other agent-related events (MessageEvent or ActionEvent)
            if isinstance(e, MessageEvent) and e.source == "agent":
                # Verify MessageEvent has the expected structure
                assert hasattr(e, "llm_message"), (
                    "MessageEvent should have llm_message attribute"
                )
                assert e.llm_message.role in ("assistant", "user"), (
                    f"Expected role to be assistant or user, got {e.llm_message.role}"
                )
                found_agent_related_event = True
            elif isinstance(e, ActionEvent) and e.source == "agent":
                # Verify ActionEvent has expected structure
                assert hasattr(e, "tool_name"), (
                    "ActionEvent should have tool_name attribute"
                )
                found_agent_related_event = True

        # We expect at least system prompt and state update events
        if found_system_prompt and found_state_update:
            break
        time.sleep(0.1)

    # Assert we got the expected events with descriptive messages
    assert found_system_prompt, (
        f"Expected to find SystemPromptEvent with source='agent'. "
        f"Found {len(state.events)} events: {
            [
                (
                    type(e).__name__,
                    e.source
                    if isinstance(e, (MessageEvent, ActionEvent, SystemPromptEvent))
                    else 'N/A',
                )
                for e in state.events
            ]
        }"
    )
    assert found_state_update, (
        f"Expected to find ConversationStateUpdateEvent. "
        f"Found {len(state.events)} events: {[type(e).__name__ for e in state.events]}"
    )
    assert found_agent_related_event, (
        f"Expected to find at least one agent-related event "
        f"(SystemPromptEvent, MessageEvent, or ActionEvent). "
        f"Found {len(state.events)} events: {
            [
                (
                    type(e).__name__,
                    e.source
                    if isinstance(
                        e,
                        (
                            MessageEvent,
                            ActionEvent,
                            SystemPromptEvent,
                            ConversationStateUpdateEvent,
                        ),
                    )
                    else 'N/A',
                )
                for e in state.events
            ]
        }"
    )

    conv.close()

    # Clean up any conversation directories that might have been created in cwd
    cwd_conversations = Path("workspace/conversations")
    if cwd_conversations.exists():
        shutil.rmtree(cwd_conversations)
