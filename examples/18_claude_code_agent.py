#!/usr/bin/env python3
# pyright: reportPossiblyUnboundVariable=false
"""
Example: Using ClaudeCodeAgent with OpenHands SDK

This example demonstrates how to use the ClaudeCodeAgent, which provides
an alternate agent implementation that uses the Claude Code SDK under the hood
while maintaining the same API/interface as the standard Agent.

Prerequisites:
- Install claude-code-sdk: pip install claude-code-sdk
- Install Claude Code CLI: npm install -g @anthropic-ai/claude-code
- Set ANTHROPIC_API_KEY environment variable

The ClaudeCodeAgent offers several advantages:
- Built-in tool execution through Claude Code
- Advanced reasoning capabilities
- Seamless integration with existing OpenHands workflows
"""

import os

from pydantic import SecretStr

from openhands.sdk.conversation import Conversation
from openhands.sdk.llm import LLM, Message, TextContent
from openhands.tools import BashTool, FileEditorTool


try:
    from openhands.sdk.agent import ClaudeCodeAgent

    CLAUDE_CODE_AVAILABLE = True
except ImportError:
    print(
        "Claude Code SDK not available. "
        "Please install with: pip install claude-code-sdk"
    )
    CLAUDE_CODE_AVAILABLE = False


def main():
    if not CLAUDE_CODE_AVAILABLE:
        return

    # Check for API key
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Please set ANTHROPIC_API_KEY environment variable")
        return

    # Create LLM instance
    llm = LLM(model="claude-3-5-sonnet-20241022", api_key=SecretStr(api_key))

    # Create tools
    tools = [
        BashTool.create(working_dir=os.getcwd()),
        FileEditorTool.create(),
    ]

    # Create Claude Code agent with custom options
    claude_options = {
        "allowed_tools": ["Read", "Write", "Bash"],  # Claude Code built-in tools
        "permission_mode": "acceptEdits",  # Auto-accept file edits
        "max_turns": 10,
    }

    agent = ClaudeCodeAgent(llm=llm, tools=tools, claude_options=claude_options)

    # Create conversation
    conversation = Conversation(agent=agent)

    print("🤖 Claude Code Agent Example")
    print("=" * 50)
    print("This agent uses Claude Code SDK for enhanced capabilities.")
    print("Type 'quit' to exit.\n")

    while True:
        try:
            user_input = input("You: ").strip()
            if user_input.lower() in ["quit", "exit", "q"]:
                break

            if not user_input:
                continue

            # Send message to agent
            message = Message(role="user", content=[TextContent(text=user_input)])
            conversation.send_message(message)

            # Run the conversation
            conversation.run()

            print()  # Add spacing between interactions

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")

    # Clean up
    conversation.close()


if __name__ == "__main__":
    main()
