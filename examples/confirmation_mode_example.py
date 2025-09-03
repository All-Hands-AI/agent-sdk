#!/usr/bin/env python3
"""
Example demonstrating confirmation mode in OpenHands Agent SDK.

This example shows how to:
1. Enable confirmation mode for an agent
2. Handle pending actions that require confirmation
3. Confirm or reject actions
4. Toggle confirmation mode during conversation
"""

import os

from pydantic import SecretStr

from openhands.core import (
    LLM,
    Agent,
    Conversation,
    LLMConfig,
    Message,
    TextContent,
    Tool,
)
from openhands.tools import BashExecutor, execute_bash_tool


def print_separator(title: str) -> None:
    """Print a separator with title."""
    print(f"\n{'=' * 60}")
    print(f" {title}")
    print(f"{'=' * 60}")


def print_pending_actions(conversation: Conversation) -> None:
    """Print all pending actions that need confirmation."""
    pending_actions = conversation.get_pending_actions()
    if not pending_actions:
        print("No pending actions.")
        return

    print(f"Found {len(pending_actions)} pending action(s):")
    for i, action in enumerate(pending_actions, 1):
        print(f"  {i}. Action ID: {action.id}")
        print(f"     Tool: {action.tool_name}")
        print(f"     Details: {str(action.action)[:100]}...")
        print()


def main() -> None:
    """Main example function."""
    print_separator("OpenHands Agent SDK - Confirmation Mode Example")

    # Initialize LLM (you can replace this with your preferred LLM)
    api_key = os.getenv("LITELLM_API_KEY", "your-api-key-here")
    llm = LLM(
        config=LLMConfig(
            model="litellm_proxy/anthropic/claude-sonnet-4-20250514",
            base_url="https://llm-proxy.eval.all-hands.dev",
            api_key=SecretStr(api_key),
        )
    )

    # Setup tools
    cwd = os.getcwd()
    bash = BashExecutor(working_dir=cwd)
    tools: list[Tool] = [
        execute_bash_tool.set_executor(executor=bash),
    ]

    # Create agent with confirmation mode enabled
    print("Creating agent with confirmation mode enabled...")
    agent = Agent(
        llm=llm,
        tools=tools,
        confirmation_mode=True,  # Enable confirmation mode
    )

    # Create conversation
    conversation = Conversation(agent=agent)

    print_separator("Step 1: Send a message that will trigger an action")

    # Send a message that will likely trigger a bash command
    user_message = Message(
        role="user",
        content=[
            TextContent(
                text="Please list the files in the current directory using ls -la"
            )
        ],
    )
    conversation.send_message(user_message)

    # Run one step - this should create an action but not execute it
    print(
        "Running agent step (should create action but not execute due to "
        "confirmation mode)..."
    )
    # Note: In confirmation mode, the agent will pause after creating actions
    # We need to manually handle the confirmation flow

    print_separator("Step 2: Check for pending actions")
    print_pending_actions(conversation)

    # Get the pending action
    pending_actions = conversation.get_pending_actions()
    if not pending_actions:
        print("No pending actions found. The agent might not have created an action.")
        return

    action_to_confirm = pending_actions[0]

    print_separator("Step 3: Demonstrate action confirmation")

    # Confirm the action
    print(f"Confirming action: {action_to_confirm.id}")
    try:
        conversation.confirm_action(action_to_confirm.id)
        print("Action confirmed and executed!")
    except Exception as e:
        print(f"Error confirming action: {e}")

    print_separator("Step 4: Send another message and demonstrate rejection")

    # Send another message
    user_message2 = Message(
        role="user",
        content=[
            TextContent(
                text=(
                    "Please create a file called 'dangerous_file.txt' with some content"
                )
            )
        ],
    )
    conversation.send_message(user_message2)

    # Run one step
    print("Running agent step for second command...")
    # Again, this will pause in confirmation mode

    # Check for new pending actions
    print("Checking for new pending actions...")
    print_pending_actions(conversation)

    pending_actions = conversation.get_pending_actions()
    if pending_actions:
        action_to_reject = pending_actions[0]

        # Reject the action
        print(f"Rejecting action: {action_to_reject.id}")
        try:
            conversation.reject_action(
                action_to_reject.id, "User decided this action is too dangerous"
            )
            print("Action rejected!")
        except Exception as e:
            print(f"Error rejecting action: {e}")

    print_separator("Step 5: Demonstrate toggling confirmation mode")

    # Disable confirmation mode
    print("Disabling confirmation mode...")
    conversation.set_confirmation_mode(False)
    print(
        f"Confirmation mode is now: "
        f"{'enabled' if agent.confirmation_mode else 'disabled'}"
    )

    # Send a message that should execute immediately
    user_message3 = Message(
        role="user",
        content=[
            TextContent(text="Please echo 'Hello from confirmation mode example!'")
        ],
    )
    conversation.send_message(user_message3)

    print("Running agent step (should execute immediately without confirmation)...")
    conversation.run()

    # Re-enable confirmation mode
    print("\nRe-enabling confirmation mode...")
    conversation.set_confirmation_mode(True)
    print(
        f"Confirmation mode is now: "
        f"{'enabled' if agent.confirmation_mode else 'disabled'}"
    )

    print_separator("Example Complete")
    print("This example demonstrated:")
    print("1. ✓ Creating an agent with confirmation mode enabled")
    print("2. ✓ Handling pending actions that require confirmation")
    print("3. ✓ Confirming actions to allow execution")
    print("4. ✓ Rejecting actions to prevent execution")
    print("5. ✓ Toggling confirmation mode during conversation")
    print("\nConfirmation mode gives you full control over which actions")
    print("your agent can execute, making it safer for production use!")


if __name__ == "__main__":
    main()
