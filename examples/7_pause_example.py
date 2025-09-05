import os
import threading
import time

from pydantic import SecretStr

from openhands.sdk import (
    LLM,
    Agent,
    Conversation,
    Message,
    TextContent,
)
from openhands.tools import (
    BashTool,
    FileEditorTool,
)


# Configure LLM
api_key = os.getenv("LITELLM_API_KEY")
assert api_key is not None, "LITELLM_API_KEY environment variable is not set."
llm = LLM(
    model="litellm_proxy/anthropic/claude-sonnet-4-20250514",
    base_url="https://llm-proxy.eval.all-hands.dev",
    api_key=SecretStr(api_key),
)

# Tools
tools = [
    BashTool(working_dir=os.getcwd()),
    FileEditorTool(),
]

# Agent
agent = Agent(llm=llm, tools=tools)
conversation = Conversation(agent)


print("Simple pause example - Press Ctrl+C to pause")

# Send a message to get the conversation started
conversation.send_message(
    Message(
        role="user",
        content=[TextContent(text="repeatedly say hello world and don't stop")],
    )
)

# Start the agent in a background thread
thread = threading.Thread(target=conversation.run)
thread.start()

try:
    # Main loop - similar to the user's sample script
    while not conversation.state.agent_finished and not conversation.state.agent_paused:
        # Send encouraging messages periodically
        conversation.send_message(
            Message(
                role="user",
                content=[TextContent(text="keep going! you can do it!")],
            )
        )
        time.sleep(1)
except KeyboardInterrupt:
    conversation.pause()

thread.join()

print(f"Agent paused: {conversation.state.agent_paused}")
