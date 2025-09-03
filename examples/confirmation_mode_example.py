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
    """Keep running conversation.run() until agent finishes."""
    while not conversation.state.agent_finished:
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

    # Run until agent finishes (may take multiple steps)
    run_until_done(conversation)

    # Check for pending actions and confirm them
    pending_actions = conversation.get_pending_actions()
    if pending_actions:
        print(
            f"Found {len(pending_actions)} pending actions. Running again to confirm..."
        )
        run_until_done(conversation)
    else:
        print("No pending actions (agent responded with message only)")

    # Example 2: Command that we'll reject
    print("\n2. Sending command that we'll reject...")
    user_message2 = Message(
        role="user",
        content=[TextContent(text="Please create a file called 'dangerous_file.txt'")],
    )
    conversation.send_message(user_message2)

    run_until_done(conversation)

    pending_actions = conversation.get_pending_actions()
    if pending_actions:
        print("Rejecting pending actions...")
        conversation.reject_pending_actions("User decided this action is too dangerous")
    else:
        print("No pending actions to reject")

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
    print("- Always run conversation.run() in a loop until agent finishes")
    print("- Check for pending actions after agent finishes")
    print("- Run again to confirm actions, or reject them")
    print("- Not every response creates actions")


if __name__ == "__main__":
    main()
