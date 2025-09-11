import os
import uuid

from pydantic import SecretStr

from openhands.sdk import (
    LLM,
    Agent,
    Conversation,
    Event,
    LLMConvertibleEvent,
    LocalFileStore,
    Message,
    TextContent,
    create_mcp_tools,
    get_logger,
)
from openhands.tools import (
    BashTool,
    FileEditorTool,
)


logger = get_logger(__name__)

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

# Add MCP Tools
mcp_config = {
    "mcpServers": {
        "fetch": {"command": "uvx", "args": ["mcp-server-fetch"]},
    }
}
mcp_tools = create_mcp_tools(mcp_config, timeout=30)
tools.extend(mcp_tools)
logger.info(f"Added {len(mcp_tools)} MCP tools")
for tool in mcp_tools:
    logger.info(f"  - {tool.name}: {tool.description}")

# Agent
agent = Agent(llm=llm, tools=tools)

llm_messages = []  # collect raw LLM messages


def conversation_callback(event: Event):
    if isinstance(event, LLMConvertibleEvent):
        llm_messages.append(event.to_llm_message())


conv_id = str(uuid.uuid4())
file_store = LocalFileStore(f"./.conversations/{conv_id}")

conversation = Conversation(
    agent=agent,
    callbacks=[conversation_callback],
    persist_filestore=file_store,
    conversation_id=conv_id,
)
conversation.send_message(
    message=Message(
        role="user",
        content=[
            TextContent(
                text=(
                    "Read https://github.com/All-Hands-AI/OpenHands. "
                    "Then write 3 facts about the project into FACTS.txt."
                )
            )
        ],
    )
)
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

# Conversation persistence
print("Serializing conversation...")

del conversation

# Deserialize the conversation
print("Deserializing conversation...")
conversation = Conversation(
    agent=agent, callbacks=[conversation_callback], persist_filestore=file_store
)

print("Sending message to deserialized conversation...")
conversation.send_message(
    message=Message(
        role="user",
        content=[
            TextContent(text="Hey what did you create? Return an agent finish action")
        ],
    )
)
conversation.run()
