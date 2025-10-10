import os

from pydantic import SecretStr

from openhands.sdk import LLM, Conversation, Event
from openhands.tools.preset.default import get_default_agent


# Configure LLM and agent
api_key = os.getenv("LLM_API_KEY")
assert api_key is not None, "LLM_API_KEY environment variable is not set."
llm = LLM(
    model="openhands/claude-sonnet-4-5-20250929",
    api_key=SecretStr(api_key),
    service_id="agent",
    drop_params=True,
)
agent = get_default_agent(llm=llm, cli_mode=True)

# Start a conversation and send some messages
cwd = os.getcwd()
conversation = Conversation(agent=agent, workspace=cwd)

# Send a message and let the agent run
conversation.send_message("Write 3 facts about the current project into FACTS.txt.")
conversation.run()
