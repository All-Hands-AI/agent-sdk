#!/usr/bin/env python3
"""
Example demonstrating confirmation mode in OpenHands Agent SDK.

This example shows how to:
1. Enable confirmation mode for an agent
2. Use conversation.run() twice for implicit confirmation
3. Use conversation.reject_pending_actions() to reject actions
4. Toggle confirmation mode during conversation
"""

import os

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
    )

    # Create conversation
    conversation = Conversation(agent=agent)
    # Enable confirmation mode at the start
    conversation.set_confirmation_mode(True)

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

    # First run() - this should create an action but not execute it
    print(
        "Running conversation.run() first time (should create action but not execute "
        "due to confirmation mode)..."
    )
    conversation.run()

    print_separator("Step 2: Check for pending actions")
    print_pending_actions(conversation)

    # Get the pending action
    pending_actions = conversation.get_pending_actions()
    if not pending_actions:
        print("No pending actions found. The agent responded with a message only.")
        print("This is normal behavior - not all agent responses create actions.")
        print(
            "For example, if the agent just says 'Hello world', no actions are needed."
        )
    else:
        print_separator("Step 3: Demonstrate implicit confirmation")

        # Second run() - this should execute the pending actions (implicit confirmation)
        print(
            "Running conversation.run() second time (should execute pending actions)..."
        )
        conversation.run()
        print("Actions executed via implicit confirmation!")

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

    # First run() - this will create new actions
    print("Running conversation.run() first time for second command...")
    conversation.run()

    # Check for new pending actions
    print("Checking for new pending actions...")
    print_pending_actions(conversation)

    pending_actions = conversation.get_pending_actions()
    if pending_actions:
        # Reject the pending actions
        print("Rejecting pending actions...")
        try:
            conversation.reject_pending_actions(
                "User decided this action is too dangerous"
            )
            print("Actions rejected!")
        except Exception as e:
            print(f"Error rejecting actions: {e}")
    else:
        print(
            "No pending actions to reject. Agent may have responded with message only."
        )

    print_separator("Step 5: Demonstrate message-only response in confirmation mode")

    # Send a message that will likely result in a simple text response
    user_message_simple = Message(
        role="user",
        content=[TextContent(text="Just say hello to me")],
    )
    conversation.send_message(user_message_simple)

    print("Running conversation.run() with a simple greeting request...")
    conversation.run()

    # Check for pending actions - there should be none for a simple greeting
    print("Checking for pending actions after simple greeting...")
    print_pending_actions(conversation)

    print_separator("Step 6: Demonstrate toggling confirmation mode")

    # Disable confirmation mode
    print("Disabling confirmation mode...")
    conversation.set_confirmation_mode(False)
    print(
        f"Confirmation mode is now: "
        f"{'enabled' if conversation.state.confirmation_mode else 'disabled'}"
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
        f"{'enabled' if conversation.state.confirmation_mode else 'disabled'}"
    )

    print_separator("Example Complete")
    print("This example demonstrated:")
    print("1. ✓ Creating an agent with confirmation mode enabled")
    print("2. ✓ Using conversation.run() twice for implicit confirmation")
    print("3. ✓ Using conversation.reject_pending_actions() to reject actions")
    print("4. ✓ Handling message-only responses (no actions created)")
    print("5. ✓ Toggling confirmation mode during conversation")
    print("\nKey insights about confirmation mode:")
    print("- Not every agent response creates actions (e.g., simple greetings)")
    print("- conversation.run() handles both scenarios gracefully:")
    print("  * Creates actions when needed (first call)")
    print("  * Executes actions when they exist (second call = implicit confirmation)")
    print("  * Finishes normally when no actions are created")
    print("- conversation.reject_pending_actions() rejects actions between calls")
    print("\nThis gives you full control over which actions your agent can execute!")


if __name__ == "__main__":
    main()
