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
    Agent,
    Conversation,
    Tool,
    get_logger,
)
from openhands.sdk.tool import register_tool
from openhands.tools.delegate import DelegateTool
from openhands.tools.preset.default import get_default_tools


logger = get_logger(__name__)

# Configure LLM and agent
# You can get an API key from https://app.all-hands.dev/settings/api-keys
api_key = os.getenv("LLM_API_KEY")
assert api_key is not None, "LLM_API_KEY environment variable is not set."
model = os.getenv("LLM_MODEL", "openhands/claude-sonnet-4-5-20250929")
llm = LLM(
    model=model,
    api_key=SecretStr(api_key),
    usage_id="agent",
)

cwd = os.getcwd()

register_tool("DelegateTool", DelegateTool)
tools = get_default_tools(enable_browser=False)
tools.append(Tool(name="DelegateTool"))

main_agent = Agent(
    llm=llm,
    tools=tools,
)

# Create conversation with the main agent
conversation = Conversation(
    agent=main_agent,
    workspace=cwd,
)

# Send the high-level task to the main agent
task_message = (
    "Forget about coding. Let's switch to travel planning. "
    "Let's plan a trip to London. I have two issues I need to solve: "
    "Lodging: what are the best areas to stay at while keeping budget in mind? "
    "Activities: what are the top 5 must-see attractions and hidden gems? "
    "Please delegate each issue to a sub-agent for analysis, then merge both "
    "analyses into a single consolidated report. "
    "Subagents should use their own knowledge and should NOT "
    "rely on internet access. They should keep it short. "
    "After spawning the sub-agents, use FinishAction to "
    "pause and wait for their results. "
    "The sub-agents will send their analysis back to you when complete.\n\n"
)

conversation.send_message(task_message)
conversation.run()


time.sleep(4)
# Wait for all delegation work to complete (with timeout)
# Access the executor through the agent's tools
executor = conversation.agent.tools_map["delegate"].executor
max_wait = 180  # 3 minutes to account for LLM processing time
start_time = time.time()

while executor.is_task_in_progress():
    elapsed = time.time() - start_time
    if elapsed >= max_wait:
        print(f"⏰ Timeout after {max_wait}s - task still in progress")
        break

    # Check every 2 seconds
    time.sleep(2)
    print("   ⏳ Task still in progress...")

if not executor.is_task_in_progress():
    print("✅ All delegation work completed successfully!")
else:
    print("⚠️  Some threads still running after timeout")
