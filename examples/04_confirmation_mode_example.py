"""OpenHands Agent SDK — Confirmation Mode Example"""

import os
import signal

from pydantic import SecretStr

from openhands.sdk import (
    LLM,
    Agent,
    Conversation,
    Message,
    TextContent,
)
from openhands.sdk.conversation.state import AgentExecutionStatus
from openhands.sdk.event.utils import get_unmatched_actions
from openhands.tools import BashTool


print("=== OpenHands Agent SDK — Confirmation Mode Example ===")

# Configure LLM
api_key = os.getenv("LITELLM_API_KEY")
assert api_key is not None, "LITELLM_API_KEY environment variable is not set."
llm = LLM(
    model="litellm_proxy/anthropic/claude-sonnet-4-20250514",
    base_url="https://llm-proxy.eval.all-hands.dev",
    api_key=SecretStr(api_key),
)

# Tools
cwd = os.getcwd()
tools = [BashTool.create(working_dir=cwd)]

# Agent and Conversation with confirmation mode enabled
agent = Agent(llm=llm, tools=tools)
conversation = Conversation(agent=agent)
conversation.set_confirmation_mode(True)

# Make ^C a clean exit instead of a stack trace
signal.signal(signal.SIGINT, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))

print("\n1) Command that will likely create actions…")
conversation.send_message(
    message=Message(
        role="user",
        content=[
            TextContent(
                text="Please list the files in the current directory using ls -la"
            )
        ],
    )
)

# Run conversation with confirmation handling
while conversation.state.agent_status != AgentExecutionStatus.FINISHED:
    # If agent is waiting for confirmation, preview actions and ask user
    if conversation.state.agent_status == AgentExecutionStatus.WAITING_FOR_CONFIRMATION:
        pending_actions = get_unmatched_actions(conversation.state.events)

        if pending_actions:
            # Build short previews for display
            print(
                f"\n🔍 Agent created {len(pending_actions)} action(s) awaiting "
                "confirmation:"
            )
            for i, action in enumerate(pending_actions, 1):
                tool = getattr(action, "tool_name", "<unknown tool>")
                snippet = str(getattr(action, "action", ""))[:100].replace("\n", " ")
                print(f"  {i}. {tool}: {snippet}…")

            # Ask for user confirmation
            while True:
                try:
                    user_input = (
                        input("\nDo you want to execute these actions? (yes/no): ")
                        .strip()
                        .lower()
                    )
                except (EOFError, KeyboardInterrupt):
                    print("\n❌ No input received; rejecting by default.")
                    user_input = "no"
                    break

                if user_input in ("yes", "y"):
                    print("✅ Approved — executing actions…")
                    break
                elif user_input in ("no", "n"):
                    print("❌ Rejected — skipping actions…")
                    conversation.reject_pending_actions("User rejected the actions")
                    break
                else:
                    print("Please enter 'yes' or 'no'.")

            if user_input in ("no", "n"):
                continue  # Loop continues — the agent may produce a new step or finish
        else:
            # Defensive: clear the flag if somehow set without actions
            print(
                "⚠️ Agent is waiting for confirmation but no pending actions were found."
            )
            conversation.state.agent_status = AgentExecutionStatus.IDLE

    print("▶️  Running conversation.run()…")
    conversation.run()

print("\n2) Command the user may choose to reject…")
conversation.send_message(
    message=Message(
        role="user",
        content=[TextContent(text="Please create a file called 'dangerous_file.txt'")],
    )
)

# Run conversation with confirmation handling
while conversation.state.agent_status != AgentExecutionStatus.FINISHED:
    if conversation.state.agent_status == AgentExecutionStatus.WAITING_FOR_CONFIRMATION:
        pending_actions = get_unmatched_actions(conversation.state.events)

        if pending_actions:
            print(
                f"\n🔍 Agent created {len(pending_actions)} action(s) awaiting "
                "confirmation:"
            )
            for i, action in enumerate(pending_actions, 1):
                tool = getattr(action, "tool_name", "<unknown tool>")
                snippet = str(getattr(action, "action", ""))[:100].replace("\n", " ")
                print(f"  {i}. {tool}: {snippet}…")

            while True:
                try:
                    user_input = (
                        input("\nDo you want to execute these actions? (yes/no): ")
                        .strip()
                        .lower()
                    )
                except (EOFError, KeyboardInterrupt):
                    print("\n❌ No input received; rejecting by default.")
                    user_input = "no"
                    break

                if user_input in ("yes", "y"):
                    print("✅ Approved — executing actions…")
                    break
                elif user_input in ("no", "n"):
                    print("❌ Rejected — skipping actions…")
                    conversation.reject_pending_actions("User rejected the actions")
                    break
                else:
                    print("Please enter 'yes' or 'no'.")

            if user_input in ("no", "n"):
                continue
        else:
            print(
                "⚠️ Agent is waiting for confirmation but no pending actions were found."
            )
            conversation.state.agent_status = AgentExecutionStatus.IDLE

    print("▶️  Running conversation.run()…")
    conversation.run()

print("\n3) Simple greeting (no actions expected)…")
conversation.send_message(
    message=Message(
        role="user",
        content=[TextContent(text="Just say hello to me")],
    )
)

# Run conversation with confirmation handling
while conversation.state.agent_status != AgentExecutionStatus.FINISHED:
    if conversation.state.agent_status == AgentExecutionStatus.WAITING_FOR_CONFIRMATION:
        pending_actions = get_unmatched_actions(conversation.state.events)

        if pending_actions:
            print(
                f"\n🔍 Agent created {len(pending_actions)} action(s) awaiting "
                "confirmation:"
            )
            for i, action in enumerate(pending_actions, 1):
                tool = getattr(action, "tool_name", "<unknown tool>")
                snippet = str(getattr(action, "action", ""))[:100].replace("\n", " ")
                print(f"  {i}. {tool}: {snippet}…")

            while True:
                try:
                    user_input = (
                        input("\nDo you want to execute these actions? (yes/no): ")
                        .strip()
                        .lower()
                    )
                except (EOFError, KeyboardInterrupt):
                    print("\n❌ No input received; rejecting by default.")
                    user_input = "no"
                    break

                if user_input in ("yes", "y"):
                    print("✅ Approved — executing actions…")
                    break
                elif user_input in ("no", "n"):
                    print("❌ Rejected — skipping actions…")
                    conversation.reject_pending_actions("User rejected the actions")
                    break
                else:
                    print("Please enter 'yes' or 'no'.")

            if user_input in ("no", "n"):
                continue
        else:
            print(
                "⚠️ Agent is waiting for confirmation but no pending actions were found."
            )
            conversation.state.agent_status = AgentExecutionStatus.IDLE

    print("▶️  Running conversation.run()…")
    conversation.run()

print("\n4) Disable confirmation mode and run a command…")
conversation.set_confirmation_mode(False)
conversation.send_message(
    message=Message(
        role="user",
        content=[
            TextContent(text="Please echo 'Hello from confirmation mode example!'")
        ],
    )
)
conversation.run()

conversation.send_message(
    message=Message(
        role="user",
        content=[
            TextContent(
                text=(
                    "Please delete any file that was created during this conversation."
                )
            )
        ],
    )
)
conversation.run()

print("\n=== Example Complete ===")
print("Key points:")
print(
    "- conversation.run() creates actions; confirmation mode sets "
    "agent_status=WAITING_FOR_CONFIRMATION"
)
print("- User confirmation is handled inline with input() prompts")
print("- Rejection uses conversation.reject_pending_actions() and continues the loop")
print("- Simple responses work normally without actions")
print("- Confirmation mode can be toggled with conversation.set_confirmation_mode()")
