"""
Example: Using ClaudeCodeAgent with the OpenHands Conversation API.

Requirements:
- claude-code-sdk (installed automatically via SDK dependency)
- Claude Code runtime requires the Node-based CLI transport at runtime:
  npm install -g @anthropic-ai/claude-code
- Set ANTHROPIC_API_KEY in the environment for the Claude Code SDK/CLI.

This example demonstrates:
- Creating a ClaudeCodeAgent
- Running a simple two-turn conversation
- Printing LLM messages collected from the event stream

Note: Claude Code’s tools (e.g., Bash/File edits) are managed internally by the
Claude Code runtime. This adapter provides compatible Conversation/Agent API
behavior, emitting MessageEvent responses.
"""

import os

from openhands.sdk import Conversation, Event, LLMConvertibleEvent, Message, TextContent
from openhands.sdk.agent import ClaudeCodeAgent
from openhands.sdk.llm import LLM
from openhands.sdk.logger import get_logger


logger = get_logger(__name__)


def main() -> None:
    # Ensure ANTHROPIC_API_KEY is set for Claude Code runtime
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    assert anthropic_key, "Please set ANTHROPIC_API_KEY in your environment."

    # LLM metadata is not used directly by Claude Code runtime, but kept for parity
    llm = LLM(model="claude-code")

    # No OpenHands tools needed; Claude Code manages its own toolset.
    agent = ClaudeCodeAgent(llm=llm, tools=[], allowed_tools=["Bash", "Read", "Write"])  # type: ignore[call-arg]

    llm_messages = []

    def on_event(e: Event) -> None:
        if isinstance(e, LLMConvertibleEvent):
            llm_messages.append(e.to_llm_message())

    conversation = Conversation(agent=agent, callbacks=[on_event])

    conversation.send_message(
        message=Message(
            role="user",
            content=[
                TextContent(
                    text=("Say hello and briefly describe what Claude Code can do.")
                )
            ],
        )
    )
    conversation.run()

    conversation.send_message(
        message=Message(
            role="user",
            content=[TextContent(text=("Thanks! That is all for now."))],
        )
    )
    conversation.run()

    print("=" * 100)
    print("Conversation finished. Got the following LLM messages:")
    for i, m in enumerate(llm_messages):
        print(f"Message {i}: {str(m)[:200]}")


if __name__ == "__main__":
    main()
