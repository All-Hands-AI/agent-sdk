"""Default experience of OpenHands Agent.

This is the *default experience* of OpenHands agent with pre-selected list of
default tools.
"""

import os

from pydantic import SecretStr

from openhands.sdk import (
    LLM,
    Agent,
    Conversation,
    Event,
    LLMConvertibleEvent,
    Message,
    TextContent,
    create_mcp_tools,
    get_logger,
)
from openhands.tools import BashTool, FileEditorTool, TaskTrackerTool


logger = get_logger(__name__)

# Configure LLM
api_key = os.getenv("LITELLM_API_KEY")
assert api_key is not None, "LITELLM_API_KEY environment variable is not set."
llm = LLM(
    model="litellm_proxy/anthropic/claude-sonnet-4-20250514",
    base_url="https://llm-proxy.eval.all-hands.dev",
    api_key=SecretStr(api_key),
)

cwd = os.getcwd()
tools = [
    BashTool.create(working_dir=cwd),
    FileEditorTool.create(),
    TaskTrackerTool.create(),
]

# Add MCP Tools
mcp_config = {
    "mcpServers": {
        "fetch": {"command": "uvx", "args": ["mcp-server-fetch"]},
        "repomix": {"command": "npx", "args": ["-y", "repomix@1.4.2", "--mcp"]},
    }
}
_mcp_tools = create_mcp_tools(config=mcp_config)
for tool in _mcp_tools:
    # Only select part of the "repomix" tools
    if "repomix" in tool.name:
        if "pack_codebase" in tool.name:
            tools.append(tool)
    else:
        tools.append(tool)
logger.info(f"Added {len(_mcp_tools)} MCP tools")
for tool in _mcp_tools:
    logger.info(f"  - {tool.name}: {tool.description}")

# Agent
agent = Agent(llm=llm, tools=tools)

llm_messages = []  # collect raw LLM messages


def conversation_callback(event: Event):
    if isinstance(event, LLMConvertibleEvent):
        llm_messages.append(event.to_llm_message())


# Conversation
conversation = Conversation(
    agent=agent,
    callbacks=[conversation_callback],
)

# Example message that can use MCP tools if available
message = Message(
    role="user",
    content=[
        TextContent(
            text="Read the current repo with repomix and "
            + "write 3 facts about the project into FACTS.txt."
        )
    ],
)

logger.info("Starting conversation with MCP integration...")
response = conversation.send_message(message)
conversation.run()

conversation.send_message(
    message=Message(
        role="user",
        content=[TextContent(text=("Great! Now delete that file."))],
    )
)
conversation.run()

print("=" * 100)
print("Conversation finished. Got the following LLM messages:")
for i, message in enumerate(llm_messages):
    print(f"Message {i}: {str(message)[:200]}")
