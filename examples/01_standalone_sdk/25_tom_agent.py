"""Example demonstrating Tom agent with Theory of Mind capabilities.

This example shows how to use the Tom agent preset which includes
a TomConsultTool for getting personalized guidance based on user modeling.
"""

import os

from pydantic import SecretStr

from openhands.sdk import LLM, Conversation
from openhands.tools.preset import get_tom_agent


# Configure LLM
api_key = os.getenv("LLM_API_KEY")
assert api_key is not None, "LLM_API_KEY environment variable is not set."

llm = LLM(
    model="openhands/claude-sonnet-4-5-20250929",
    api_key=SecretStr(api_key),
    service_id="agent",
    drop_params=True,
)

# Create Tom agent with Theory of Mind capabilities
# This agent can consult Tom for personalized guidance
# Note: Tom's user modeling data will be stored in workspace/.openhands/
agent = get_tom_agent(
    llm=llm,
    cli_mode=True,  # Disable browser tools for CLI
    enable_rag=True,  # Enable RAG in Tom agent
)

# Start conversation
cwd = os.getcwd()
conversation = Conversation(agent=agent, workspace=cwd)

# Send a potentially vague message where Tom consultation might help
conversation.send_message(
    "I need to debug some code but I'm not sure where to start. "
    "Can you help me figure out the best approach?"
)
conversation.run()

print("\n" + "=" * 80)
print("Tom agent consultation example completed!")
print("=" * 80)
