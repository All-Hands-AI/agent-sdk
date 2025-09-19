from __future__ import annotations

from typing import Any, Iterable, cast

import anyio
from pydantic import Field

from openhands.sdk.agent.base import AgentBase
from openhands.sdk.conversation import ConversationCallbackType, ConversationState
from openhands.sdk.event import LLMConvertibleEvent, MessageEvent, SystemPromptEvent
from openhands.sdk.llm import Message, TextContent
from openhands.sdk.logger import get_logger


logger = get_logger(__name__)


class ClaudeCodeAgent(AgentBase):
    """Alternate Agent that uses Anthropics' Claude Code Python SDK under the hood.

    It conforms to the same AgentBase API (init_state/step) so it can be used with
    Conversation unchanged.

    Notes:
    - This minimal integration treats Claude Code as a self-contained assistant.
      Tool invocations (Bash/File edits) are handled by Claude Code CLI itself and
      are not surfaced as Tool/Observation events in our SDK. The step produces a
      single assistant MessageEvent per user turn.
    - Tests stub the SDK to avoid requiring Node/CLI.
    """

    # Optional: allow specifying Claude Code allowed tools explicitly
    allowed_tools: list[str] = Field(default_factory=list)

    def _latest_user_message(
        self, events: Iterable[LLMConvertibleEvent]
    ) -> Message | None:
        last: Message | None = None
        for e in events:
            if isinstance(e, MessageEvent) and e.source == "user":
                last = e.to_llm_message()
        return last

    def init_state(
        self,
        state: ConversationState,
        on_event: ConversationCallbackType,
    ) -> None:
        # Emit system prompt event once
        llm_events = [e for e in state.events if isinstance(e, LLMConvertibleEvent)]
        if len(llm_events) == 0:
            event = SystemPromptEvent(
                source="agent",
                system_prompt=TextContent(text=self.system_message),
                tools=[],  # Claude Code tools are managed internally
            )
            on_event(event)

    def _build_options(self, state: ConversationState):
        # Import lazily to avoid import cost if unused and to keep optional dep flexible
        from claude_code_sdk import ClaudeCodeOptions

        allowed: list[str] = list(self.allowed_tools)
        # If user provided familiar tools, enable matching Claude Code tools
        try:
            if isinstance(self.tools, dict):
                names = set(self.tools.keys())
                if "execute_bash" in names and "Bash" not in allowed:
                    allowed.append("Bash")
                # If editor-like tools exist, enable read/write
                if any(
                    n in names
                    for n in ("str_replace_editor", "file_editor_tool", "file_editor")
                ):
                    if "Read" not in allowed:
                        allowed.append("Read")
                    if "Write" not in allowed:
                        allowed.append("Write")
        except Exception:  # pragma: no cover - best-effort only
            pass

        # Map working directory: prefer cwd of current process
        import os

        cwd = os.getcwd()

        return ClaudeCodeOptions(
            allowed_tools=allowed,
            system_prompt=self.system_message,
            model=self.llm.model if hasattr(self.llm, "model") else None,
            cwd=cwd,
        )

    async def _query_once_async(self, prompt: str, options: Any) -> str:
        """Run one Claude Code query and collect assistant text.

        Returns the concatenated assistant text content blocks for the response.
        """
        from claude_code_sdk import AssistantMessage, TextBlock, query

        chunks: list[str] = []
        async for msg in query(prompt=prompt, options=options):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        chunks.append(block.text)
        return "".join(chunks)

    def step(
        self,
        state: ConversationState,
        on_event: ConversationCallbackType,
    ) -> None:
        # Build options per turn (captures latest system prompt, cwd, tools)
        options = self._build_options(state)

        # Find latest user message; if none, do nothing
        llm_events = cast(
            list[LLMConvertibleEvent],
            [e for e in state.events if isinstance(e, LLMConvertibleEvent)],
        )
        last_user = self._latest_user_message(llm_events)
        if last_user is None:
            logger.info("ClaudeCodeAgent.step called without a user message; skipping")
            return

        # Convert user message to plain text prompt
        prompt_parts = [c.text for c in last_user.content if isinstance(c, TextContent)]
        prompt = "\n".join(prompt_parts)

        # Run async SDK in a temporary event loop and get response text
        try:
            response_text = anyio.run(self._query_once_async, prompt, options)
        except Exception as e:  # pragma: no cover - transport/runtime errors
            logger.exception("Claude Code SDK query failed: %s", e)
            response_text = f"[Claude Code error] {e}"

        # Emit assistant message and finish the turn
        msg_event = MessageEvent(
            source="agent",
            llm_message=Message(
                role="assistant", content=[TextContent(text=response_text)]
            ),
            metrics=None,
        )
        on_event(msg_event)
        # Finish turn; await next user input
        from openhands.sdk.conversation.state import AgentExecutionStatus

        state.agent_status = AgentExecutionStatus.FINISHED
