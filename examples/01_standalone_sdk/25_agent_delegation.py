"""
Agent Delegation Example

This example demonstrates the agent delegation feature where a main agent
delegates tasks to sub-agents for parallel processing.
Each sub-agent runs independently and returns its results to the main agent,
which then merges both analyses into a single consolidated report.
"""

import os
import time

from pydantic import SecretStr

from openhands.sdk import (
    LLM,
    Conversation,
    get_logger,
)
from openhands.sdk.conversation.state import AgentExecutionStatus
from openhands.sdk.delegation.manager import DelegationManager
from openhands.tools.preset.default import get_default_agent


logger = get_logger(__name__)

# Configure LLM and agent
# You can get an API key from https://app.all-hands.dev/settings/api-keys
api_key = os.getenv("LLM_API_KEY")
assert api_key is not None, "LLM_API_KEY environment variable is not set."
model = os.getenv("LLM_MODEL", "openhands/claude-sonnet-4-5-20250929")
base_url = os.getenv("LLM_BASE_URL")
llm = LLM(
    model=model,
    api_key=SecretStr(api_key),
    base_url=base_url,
    usage_id="agent",
)

cwd = os.getcwd()


# Initialize main agent with delegation capabilities
main_agent = get_default_agent(llm=llm, enable_delegation=True, cli_mode=True)

# Create conversation with the main agent
conversation = Conversation(
    agent=main_agent,
    workspace=cwd,
)

# Register the conversation with the singleton delegation manager
# This allows the delegate tool to look up the parent conversation by ID
delegation_manager = DelegationManager()
delegation_manager.register_conversation(conversation)

# Send the high-level task to the main agent
task_message = (
    "Forget about coding. Let's switch to travel planning. "
    "Let's plan a trip to London. I have two issues I need to solve: "
    "Lodging: what are the best areas to stay at while keeping budget in mind? "
    "Activities: what are the top 5 must-see attractions and hidden gems? "
    "Please delegate each issue to a sub-agent for analysis, then merge both "
    "analyses into a single consolidated report. Use your own knowledge, don't "
    "rely on internet access. Keep it short."
)

conversation.send_message(task_message)
conversation.run()


time.sleep(4)
while conversation.state.agent_status != AgentExecutionStatus.FINISHED:
    time.sleep(2)
    print("   ⏳ Task still in progress...")

print("✅ All delegation work completed successfully!")
