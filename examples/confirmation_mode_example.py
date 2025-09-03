#!/usr/bin/env python3
"""
Simplified example demonstrating confirmation mode in OpenHands Agent SDK.

This example shows how to:
1. Enable confirmation mode for an agent
2. Use conversation.run() in a loop until agent finishes
3. Handle implicit confirmation and rejection
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


def run_until_done(conversation: Conversation) -> None:
    """Keep running conversation.run() until agent finishes.

    In confirmation mode, this will:
    1. Check if agent is waiting for confirmation before each run
    2. If waiting, ask user for yes/no input
    3. If approved, run conversation.run() to execute actions
    4. If rejected, call reject_pending_actions()
    """
    while not conversation.state.agent_finished:
        # Check if agent is waiting for confirmation BEFORE running
        if conversation.state.waiting_for_confirmation:
            pending_actions = conversation.get_pending_actions()
            if pending_actions:
                print(
                    f"\n🔍 Agent created {len(pending_actions)} action(s) "
                    "and is waiting for confirmation:"
                )
                for i, action in enumerate(pending_actions, 1):
                    action_preview = str(action.action)[:100]
                    print(f"  {i}. {action.tool_name}: {action_preview}...")

                # Ask user for confirmation
                while True:
                    user_input = (
                        input("\nDo you want to execute these actions? (yes/no): ")
                        .strip()
                        .lower()
                    )
                    if user_input in ["yes", "y"]:
                        print("✅ User approved - executing actions...")
                        # Continue to run() which will execute the actions
                        break
                    elif user_input in ["no", "n"]:
                        print("❌ User rejected - rejecting actions...")
                        conversation.reject_pending_actions("User rejected the actions")
                        # Continue the loop to check if agent is finished
                        continue
                    else:
                        print("Please enter 'yes' or 'no'")
            else:
                # This shouldn't happen, but handle gracefully
                print(
                    "⚠️  Agent is waiting for confirmation but no pending actions found"
                )
                conversation.state.waiting_for_confirmation = False

        print("Running conversation.run()...")
        conversation.run()


def main() -> None:
    """Main example function."""
    print("=== OpenHands Agent SDK - Confirmation Mode Example ===")

    # Initialize LLM
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

    # Create agent and conversation
    agent = Agent(llm=llm, tools=tools)
    conversation = Conversation(agent=agent)
    conversation.set_confirmation_mode(True)

    # Example 1: Command that creates actions
    print("\n1. Sending command that will create actions...")
    user_message = Message(
        role="user",
        content=[
            TextContent(
                text="Please list the files in the current directory using ls -la"
            )
        ],
    )
    conversation.send_message(user_message)

    # Run until agent finishes - will automatically handle confirmation
    run_until_done(conversation)

    # Example 2: Command that we can reject (user will be prompted)
    print("\n2. Sending command that user can choose to reject...")
    user_message2 = Message(
        role="user",
        content=[TextContent(text="Please create a file called 'dangerous_file.txt'")],
    )
    conversation.send_message(user_message2)

    # Run until agent finishes - user will be prompted to approve/reject
    run_until_done(conversation)

    # Example 3: Simple greeting (no actions expected)
    print("\n3. Sending simple greeting...")
    user_message3 = Message(
        role="user",
        content=[TextContent(text="Just say hello to me")],
    )
    conversation.send_message(user_message3)

    run_until_done(conversation)

    # Example 4: Disable confirmation mode
    print("\n4. Disabling confirmation mode and running command...")
    conversation.set_confirmation_mode(False)

    user_message4 = Message(
        role="user",
        content=[
            TextContent(text="Please echo 'Hello from confirmation mode example!'")
        ],
    )
    conversation.send_message(user_message4)

    run_until_done(conversation)

    print("\n=== Example Complete ===")
    print("Key points:")
    print("- conversation.run() creates actions and sets waiting_for_confirmation=True")
    print("- Example detects this flag and prompts user for yes/no confirmation")
    print("- User approval leads to implicit confirmation (second run() call)")
    print("- User rejection calls reject_pending_actions() and clears the flag")
    print("- Not every response creates actions (simple greetings work normally)")


if __name__ == "__main__":
    main()
