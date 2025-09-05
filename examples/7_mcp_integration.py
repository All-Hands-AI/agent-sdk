import asyncio
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
    get_logger,
)
from openhands.sdk.config.mcp_config import MCPConfig, MCPStdioServerConfig
from openhands.sdk.mcp.utils import create_mcp_tools_from_config
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

# Configure MCP servers
mcp_config = MCPConfig(
    stdio_servers=[
        MCPStdioServerConfig(
            name="fetch",
            command="uvx",
            args=["mcp-server-fetch"],
        )
    ]
)

# Tools
cwd = os.getcwd()
tools: list[Tool] = [
    BashTool(working_dir=cwd),
    FileEditorTool(),
]

# Add MCP tools if available
try:
    mcp_tools = asyncio.run(create_mcp_tools_from_config(mcp_config, timeout=10.0))
    tools.extend(mcp_tools)
    logger.info(f"Added {len(mcp_tools)} MCP tools")
    for tool in mcp_tools:
        logger.info(f"  - {tool.name}: {tool.description}")
except Exception as e:
    logger.warning(f"Failed to load MCP tools: {e}")
    logger.info("Continuing with standard tools only")

# Agent
agent = Agent(llm=llm, tools=tools)

llm_messages = []  # collect raw LLM messages


def conversation_callback(event: EventType):
    logger.info(f"Found a conversation message: {str(event)[:200]}...")
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
