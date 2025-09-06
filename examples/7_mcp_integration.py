import os

from pydantic import SecretStr

from openhands.sdk import (
    LLM,
    Agent,
    Conversation,
    EventType,
    LLMConvertibleEvent,
    Message,
    TextContent,
    Tool,
    create_mcp_tools,
    get_logger,
)
from openhands.tools import BashTool, FileEditorTool


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
tools: list[Tool] = [
    BashTool(working_dir=cwd),
    FileEditorTool(),
]

# Add MCP Tools
mcp_config = {"mcpServers": {"fetch": {"command": "uvx", "args": ["mcp-server-fetch"]}}}
mcp_tools = create_mcp_tools(mcp_config, timeout=30)
tools.extend(mcp_tools)
logger.info(f"Added {len(mcp_tools)} MCP tools")
for tool in mcp_tools:
    logger.info(f"  - {tool.name}: {tool.description}")


# Agent
agent = Agent(llm=llm, tools=tools)

llm_messages = []  # collect raw LLM messages


def conversation_callback(event: EventType):
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
            text="Read https://github.com/All-Hands-AI/OpenHands and "
            + "write 3 facts about the project into FACTS.txt."
        )
    ],
)

logger.info("Starting conversation with MCP integration...")
response = conversation.send_message(message)
conversation.run()

print("=" * 100)
print("Conversation finished. Got the following LLM messages:")
for i, message in enumerate(llm_messages):
    print(f"Message {i}: {str(message)[:200]}")
