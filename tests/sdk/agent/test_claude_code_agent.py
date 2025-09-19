from typing import Any, AsyncIterator
from unittest.mock import patch

import pytest

from openhands.sdk.agent import ClaudeCodeAgent
from openhands.sdk.conversation import Conversation
from openhands.sdk.llm import LLM, Message, TextContent


class _DummyAssistantMessage:
    def __init__(self, text: str):
        self.content = [_DummyTextBlock(text)]


class _DummyTextBlock:
    def __init__(self, text: str):
        self.text = text


@pytest.fixture
def agent() -> ClaudeCodeAgent:
    llm = LLM(model="claude-code")
    return ClaudeCodeAgent(llm=llm, tools=[], allowed_tools=["Bash"])  # minimal


def _dummy_query(
    *, prompt: str | Any, options: Any, transport: Any | None = None
) -> AsyncIterator[Any]:
    async def _gen() -> AsyncIterator[Any]:
        # Emit a single assistant message with text
        yield _DummyAssistantMessage(text=f"echo: {prompt}")

    return _gen()


def test_init_state_emits_system_prompt(agent: ClaudeCodeAgent):
    with (
        patch("claude_code_sdk.query", new=_dummy_query),
        patch("claude_code_sdk.AssistantMessage", _DummyAssistantMessage),
        patch("claude_code_sdk.TextBlock", _DummyTextBlock),
    ):
        conv = Conversation(agent)
        # First event should be a system prompt
        sys_events = [
            e for e in conv.state.events if e.__class__.__name__ == "SystemPromptEvent"
        ]
        assert len(sys_events) == 1
        assert "System Prompt" in sys_events[0].visualize.plain


def test_step_round_trip(agent: ClaudeCodeAgent):
    with (
        patch("claude_code_sdk.query", new=_dummy_query),
        patch("claude_code_sdk.AssistantMessage", _DummyAssistantMessage),
        patch("claude_code_sdk.TextBlock", _DummyTextBlock),
    ):
        conv = Conversation(agent)
        # Send a user message
        conv.send_message(Message(role="user", content=[TextContent(text="hello")]))
        conv.run()

        # Should have produced an assistant message with echoed text
        msgs = [
            e
            for e in conv.state.events
            if e.__class__.__name__ == "MessageEvent" and e.source == "agent"
        ]
        assert len(msgs) >= 1
        assert "echo: hello" in msgs[-1].visualize.plain
