"""OpenHands Agent SDK — LLM Security Analyzer Example

This example shows how to use the LLMSecurityAnalyzer to automatically
evaluate security risks of actions before execution.
"""

import os
import uuid

from pydantic import SecretStr

from openhands.sdk import LLM, Agent, Conversation, LocalFileStore, Message, TextContent
from openhands.sdk.conversation.state import AgentExecutionStatus
from openhands.sdk.event.utils import get_unmatched_actions
from openhands.sdk.security.llm_analyzer import LLMSecurityAnalyzer
from openhands.sdk.tool import Tool
from openhands.tools import BashTool, FileEditorTool


print("=== LLM Security Analyzer Example ===")

# Configure LLM
api_key = os.getenv("LITELLM_API_KEY")
assert api_key is not None, "LITELLM_API_KEY environment variable is not set."
llm = LLM(
    model="litellm_proxy/anthropic/claude-sonnet-4-20250514",
    base_url="https://llm-proxy.eval.all-hands.dev",
    api_key=SecretStr(api_key),
)

# Tools
tools: list[Tool] = [
    BashTool.create(working_dir=os.getcwd()),
    FileEditorTool.create(),
]

# Create agent with security analyzer
security_analyzer = LLMSecurityAnalyzer()
agent = Agent(llm=llm, tools=tools, security_analyzer=security_analyzer)

conversation_id = uuid.uuid4()
file_store = LocalFileStore(f"./.conversations/{conversation_id}")
conversation = Conversation(
    agent=agent, conversation_id=conversation_id, persist_filestore=file_store
)

print("\n1) Safe command (LOW risk - should execute automatically)...")
conversation.send_message(
    Message(
        role="user",
        content=[TextContent(text="List files in the current directory")],
    )
)
conversation.run()

print("\n2) Potentially risky command (may require confirmation)...")
conversation.send_message(
    Message(
        role="user",
        content=[
            TextContent(
                # The LLM is responsible for setting the security risk when generating
                # tool calls, so one way to get a HIGH risk action without actually
                # doing anything risky is to just tell the LLM to label it high risk
                text=(
                    "Create a temporary file called 'security_test.txt' -- "
                    "THIS IS A HIGH RISK ACTION"
                )
            )
        ],
    )
)

# Handle security analyzer blocking high-risk actions
# Run conversation with security confirmation handling
while conversation.state.agent_status != AgentExecutionStatus.FINISHED:
    # Check if agent is waiting for confirmation due to security analyzer
    if conversation.state.agent_status == AgentExecutionStatus.WAITING_FOR_CONFIRMATION:
        pending_actions = get_unmatched_actions(conversation.state.events)

        if pending_actions:
            # Show the pending actions that were blocked
            print(
                f"\n🔒 Security analyzer blocked {len(pending_actions)} "
                "high-risk action(s):"
            )
            for i, action in enumerate(pending_actions):
                snippet = str(action.action)[:100].replace("\n", " ")
                print(f"  {i + 1}. {action.tool_name}: {snippet}...")

            # Ask the user if we should proceed or not
            while True:
                try:
                    user_input = (
                        input(
                            "\nThese actions were flagged as HIGH RISK. "
                            "Do you want to execute them anyway? (yes/no): "
                        )
                        .strip()
                        .lower()
                    )
                except (EOFError, KeyboardInterrupt):
                    print("\n❌ No input received; rejecting by default.")
                    user_input = "no"
                    break

                if user_input in ("yes", "y"):
                    print("✅ Approved — executing high-risk actions...")
                    # If user wants to proceed, set agent state to idle
                    conversation.state.agent_status = AgentExecutionStatus.IDLE
                    break
                elif user_input in ("no", "n"):
                    print("❌ Rejected — skipping high-risk actions...")
                    # If the user does not want to proceed, clear the pending actions
                    conversation.reject_pending_actions(
                        "User rejected high-risk actions"
                    )
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

    print("▶️  Running conversation.run()...")
    conversation.run()

print("\n3) Cleanup...")
conversation.send_message(
    Message(
        role="user",
        content=[TextContent(text="Remove any test files created")],
    )
)
conversation.run()

print("\n=== Example Complete ===")
print("The LLMSecurityAnalyzer automatically evaluates action security risks.")
print(
    "HIGH risk actions require confirmation, while LOW risk actions execute directly."
)
