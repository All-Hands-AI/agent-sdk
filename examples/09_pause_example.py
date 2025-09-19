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
from openhands.sdk.conversation.state import AgentExecutionStatus
from openhands.tools.execute_bash import BashTool
from openhands.tools.str_replace_editor import FileEditorTool


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
    BashTool.create(working_dir=os.getcwd()),
    FileEditorTool.create(),
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
    while (
        conversation.state.agent_status != AgentExecutionStatus.FINISHED
        and conversation.state.agent_status != AgentExecutionStatus.PAUSED
    ):
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

print(f"Agent status: {conversation.state.agent_status}")
