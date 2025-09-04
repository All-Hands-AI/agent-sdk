#!/usr/bin/env python3
"""
OpenHands Agent SDK — Confirmation Mode Example
"""

from __future__ import annotations

import os
import signal
from typing import Iterable, Optional

from pydantic import SecretStr

from openhands.sdk import (
    LLM,
    Agent,
    Conversation,
    LLMConfig,
    Message,
    TextContent,
    Tool,
)
from openhands.tools import BashExecutor, execute_bash_tool


# ---------------------------
# Setup helpers
# ---------------------------


def build_llm() -> LLM:
    api_key = os.getenv("LITELLM_API_KEY") or "fake-key"
    model = os.getenv("LITELLM_MODEL") or "gpt-4o-mini"
    llm = LLM(
        config=LLMConfig(
            model=model,
            api_key=SecretStr(api_key),
        )
    )
    return llm


def build_tools(cwd: Optional[str] = None) -> list[Tool]:
    cwd = cwd or os.getcwd()
    bash = BashExecutor(working_dir=cwd)
    return [execute_bash_tool.set_executor(executor=bash)]


def make_conversation(
    llm: LLM, tools: Iterable[Tool], confirmation: bool = True
) -> Conversation:
    agent = Agent(llm=llm, tools=list(tools))
    convo = Conversation(agent=agent)
    convo.set_confirmation_mode(confirmation)
    return convo


# ---------------------------
# User interaction
# ---------------------------


def ask_user_confirmation(pending_count: int, previews: list[str]) -> bool:
    """
    Prompt the user to approve or reject pending actions.
    Returns True if approved, False if rejected.
    """
    print(
        f"\n🔍 Agent created {pending_count} action(s) and is waiting for confirmation:"
    )
    for i, preview in enumerate(previews, 1):
        print(f"  {i}. {preview}")

    while True:
        try:
            user_input = (
                input("\nDo you want to execute these actions? (yes/no): ")
                .strip()
                .lower()
            )
        except (EOFError, KeyboardInterrupt):
            print("\n❌ No input received; rejecting by default.")
            return False

        if user_input in ("yes", "y"):
            print("✅ Approved — executing actions…")
            return True
        if user_input in ("no", "n"):
            print("❌ Rejected — skipping actions…")
            return False
        print("Please enter 'yes' or 'no'.")


# ---------------------------
# Conversation runner
# ---------------------------


def run_until_done(conversation: Conversation) -> None:
    """
    Keep running conversation.run() until the agent finishes.
    If the agent is waiting for confirmation, ask the user and either proceed
    or reject the pending actions.
    """

    # Make ^C a clean exit instead of a stack trace.
    signal.signal(signal.SIGINT, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))

    while not conversation.state.agent_finished:
        # If agent is waiting for confirmation, preview actions and ask user
        if conversation.state.waiting_for_confirmation:
            pending_actions = conversation.get_pending_actions()

            if pending_actions:
                # Build short previews for display
                previews = []
                for a in pending_actions:
                    tool = getattr(a, "tool_name", "<unknown tool>")
                    snippet = str(getattr(a, "action", ""))[:100].replace("\n", " ")
                    previews.append(f"{tool}: {snippet}…")

                approved = ask_user_confirmation(len(pending_actions), previews)
                if not approved:
                    conversation.reject_pending_actions("User rejected the actions")
                    # Loop continues — the agent may produce a new step or finish
                    continue
                # If approved: fall through to run() which will execute actions
            else:
                # Defensive: clear the flag if somehow set without actions
                print(
                    "⚠️ Agent is waiting for confirmation but no pending actions "
                    "were found."
                )
                conversation.state.waiting_for_confirmation = False

        print("▶️  Running conversation.run()…")
        conversation.run()


# ---------------------------
# Scripted examples
# ---------------------------


def send_and_run(conversation: Conversation, text: str) -> None:
    """Convenience wrapper to send a user message and run until done."""
    msg = Message(role="user", content=[TextContent(text=text)])
    conversation.send_message(msg)
    run_until_done(conversation)


def main() -> None:
    print("=== OpenHands Agent SDK — Confirmation Mode (Modular) ===")

    llm = build_llm()
    tools = build_tools()

    # 1) Start with confirmation mode ON
    conversation = make_conversation(llm, tools, confirmation=True)

    print("\n1) Command that will likely create actions…")
    send_and_run(
        conversation, "Please list the files in the current directory using ls -la"
    )

    print("\n2) Command the user may choose to reject…")
    send_and_run(conversation, "Please create a file called 'dangerous_file.txt'")

    print("\n3) Simple greeting (no actions expected)…")
    send_and_run(conversation, "Just say hello to me")

    print("\n4) Disable confirmation mode and run a command…")
    conversation.set_confirmation_mode(False)
    send_and_run(conversation, "Please echo 'Hello from confirmation mode example!'")

    print("\n=== Example Complete ===")
    print("Key points:")
    print(
        "- conversation.run() creates actions; confirmation mode sets "
        "waiting_for_confirmation=True"
    )
    print("- ask_user_confirmation() centralizes the yes/no prompt")
    print(
        "- Rejection uses conversation.reject_pending_actions() and continues the loop"
    )
    print("- Simple responses work normally without actions")


if __name__ == "__main__":
    main()
