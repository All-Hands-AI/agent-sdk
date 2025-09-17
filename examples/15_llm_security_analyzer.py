"""OpenHands Agent SDK — LLM Security Analyzer Example

This example demonstrates how to use the LLMSecurityAnalyzer to evaluate
the security risk of actions before they are executed. The LLM security
analyzer leverages the security_risk attribute that can be set by the LLM
when generating actions.

Key features demonstrated:
- Setting up an agent with LLM security analyzer
- How different security risk levels affect confirmation requirements
- Analyzing pending actions for security risks
- Custom security risk handling and reporting
"""

import os
import signal
from typing import Any

from pydantic import SecretStr

from openhands.sdk import (
    LLM,
    Agent,
    Conversation,
    Message,
    TextContent,
    get_logger,
)
from openhands.sdk.conversation.state import AgentExecutionStatus
from openhands.sdk.event.utils import get_unmatched_actions
from openhands.sdk.security.llm_analyzer import LLMSecurityAnalyzer
from openhands.sdk.security.risk import SecurityRisk
from openhands.tools import BashTool, FileEditorTool


logger = get_logger(__name__)

print("=== OpenHands Agent SDK — LLM Security Analyzer Example ===")

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
tools = [
    BashTool.create(working_dir=cwd),
    FileEditorTool.create(),
]

# Create LLM Security Analyzer
security_analyzer = LLMSecurityAnalyzer()

# Agent with security analyzer
agent = Agent(llm=llm, tools=tools, security_analyzer=security_analyzer)
conversation = Conversation(agent=agent)

# Make ^C a clean exit instead of a stack trace
signal.signal(signal.SIGINT, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))


def display_security_analysis(pending_actions: list[Any]) -> None:
    """Display security analysis results for pending actions."""
    if not pending_actions:
        print("  No pending actions to analyze.")
        return

    print(f"  📊 Security Analysis Results ({len(pending_actions)} actions):")

    # Analyze actions using the security analyzer
    analysis_results = security_analyzer.analyze_pending_actions(pending_actions)

    for i, (action_event, risk) in enumerate(analysis_results, 1):
        tool_name = getattr(action_event, "tool_name", "unknown")
        action_snippet = str(getattr(action_event.action, "command", ""))[:60]
        if len(action_snippet) > 60:
            action_snippet += "..."

        risk_emoji = {
            SecurityRisk.LOW: "🟢",
            SecurityRisk.MEDIUM: "🟡",
            SecurityRisk.HIGH: "🔴",
            SecurityRisk.UNKNOWN: "⚪",
        }.get(risk, "❓")

        print(f"    {i}. {risk_emoji} {risk.name} - {tool_name}: {action_snippet}")
        print(f"       {risk.description}")


def handle_confirmation_with_security_analysis() -> bool:
    """Handle confirmation with detailed security analysis display."""
    pending_actions = get_unmatched_actions(conversation.state.events)

    if not pending_actions:
        print("⚠️ Agent is waiting for confirmation but no pending actions found.")
        conversation.state.agent_status = AgentExecutionStatus.IDLE
        return False

    print(f"\n🔍 Agent created {len(pending_actions)} action(s) awaiting confirmation:")
    display_security_analysis(pending_actions)

    # Ask for user confirmation
    while True:
        try:
            user_input = (
                input("\nDo you want to execute these actions? (yes/no/analyze): ")
                .strip()
                .lower()
            )
        except (EOFError, KeyboardInterrupt):
            print("\n❌ No input received; rejecting by default.")
            conversation.reject_pending_actions("User interrupted input")
            return False

        if user_input in ("yes", "y"):
            print("✅ Approved — executing actions…")
            return True
        elif user_input in ("no", "n"):
            print("❌ Rejected — skipping actions…")
            conversation.reject_pending_actions("User rejected the actions")
            return False
        elif user_input in ("analyze", "a"):
            print("\n📋 Detailed Security Analysis:")
            display_security_analysis(pending_actions)
            continue
        else:
            print("Please enter 'yes', 'no', or 'analyze'.")


print("\n1) Testing LOW risk command (should not require confirmation)...")
conversation.send_message(
    message=Message(
        role="user",
        content=[
            TextContent(
                text=(
                    "Please list the files in the current directory. "
                    "This is a safe read-only operation with LOW security risk."
                )
            )
        ],
    )
)

# Run with security analysis
while conversation.state.agent_status != AgentExecutionStatus.FINISHED:
    if conversation.state.agent_status == AgentExecutionStatus.WAITING_FOR_CONFIRMATION:
        if not handle_confirmation_with_security_analysis():
            continue

    print("▶️  Running conversation.run()…")
    conversation.run()

print("\n2) Testing MEDIUM risk command (may require confirmation)...")
conversation.send_message(
    message=Message(
        role="user",
        content=[
            TextContent(
                text=(
                    "Please create a temporary file called 'test_security.txt' with "
                    "some sample content. This has MEDIUM security risk as it modifies "
                    "the filesystem."
                )
            )
        ],
    )
)

# Run with security analysis
while conversation.state.agent_status != AgentExecutionStatus.FINISHED:
    if conversation.state.agent_status == AgentExecutionStatus.WAITING_FOR_CONFIRMATION:
        if not handle_confirmation_with_security_analysis():
            continue

    print("▶️  Running conversation.run()…")
    conversation.run()

print("\n3) Testing HIGH risk command (should always require confirmation)...")
conversation.send_message(
    message=Message(
        role="user",
        content=[
            TextContent(
                text=(
                    "Please run a command that could potentially be dangerous, "
                    "like deleting files or modifying system settings. "
                    "This should be marked as HIGH security risk."
                )
            )
        ],
    )
)

# Run with security analysis
while conversation.state.agent_status != AgentExecutionStatus.FINISHED:
    if conversation.state.agent_status == AgentExecutionStatus.WAITING_FOR_CONFIRMATION:
        if not handle_confirmation_with_security_analysis():
            continue

    print("▶️  Running conversation.run()…")
    conversation.run()

print("\n4) Demonstrating security analyzer capabilities...")

# Show how to manually analyze actions
print("\n📊 Manual Security Analysis Example:")
print("The LLMSecurityAnalyzer evaluates actions based on the security_risk")
print("attribute set by the LLM. Here's how it works:")

# Get any pending actions for demonstration
pending_actions = get_unmatched_actions(conversation.state.events)
if pending_actions:
    print(f"\nAnalyzing {len(pending_actions)} pending actions:")
    display_security_analysis(pending_actions)
else:
    print("\nNo pending actions to analyze at this time.")

print("\n5) Security risk level descriptions:")
for risk_level in [
    SecurityRisk.LOW,
    SecurityRisk.MEDIUM,
    SecurityRisk.HIGH,
    SecurityRisk.UNKNOWN,
]:
    print(f"  {risk_level.name}: {risk_level.description}")

print("\n6) Cleanup - removing test files...")
conversation.send_message(
    message=Message(
        role="user",
        content=[
            TextContent(
                text="Please remove any test files created during this example."
            )
        ],
    )
)

# Run cleanup without detailed confirmation handling
conversation.run()

print("\n=== Example Complete ===")
print("\nKey takeaways about LLM Security Analyzer:")
print("• The LLMSecurityAnalyzer reads the security_risk attribute from actions")
print("• Risk levels: LOW (safe), MEDIUM (review), HIGH (confirm), UNKNOWN (unclear)")
print("• HIGH risk actions always require confirmation")
print("• UNKNOWN risk actions require confirmation when no analyzer is configured")
print("• The analyzer integrates seamlessly with the conversation confirmation flow")
print("• Security analysis helps users make informed decisions about action execution")
print("• The LLM can set appropriate risk levels based on action content and context")

# Clean up the security analyzer
security_analyzer.close()
