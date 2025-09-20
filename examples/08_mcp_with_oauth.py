import os

from pydantic import SecretStr

from openhands.sdk import (
    LLM,
    Agent,
    Conversation,
    EventBase,
    LLMConvertibleEvent,
    Message,
    TextContent,
    create_mcp_tools,
    get_logger,
)
from openhands.sdk.tool import ToolSpec, register_tool
from openhands.tools.execute_bash import BashTool
from openhands.tools.str_replace_editor import FileEditorTool


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
register_tool("BashTool", BashTool)
register_tool("FileEditorTool", FileEditorTool)
tool_specs = [
    ToolSpec(name="BashTool", params={"working_dir": cwd}),
    ToolSpec(name="FileEditorTool", params={}),
]

# Add MCP Tools
mcp_config = {
    "mcpServers": {"Notion": {"url": "https://mcp.notion.com/mcp", "auth": "oauth"}}
}
mcp_tools = create_mcp_tools(mcp_config, timeout=30)
logger.info(f"Added {len(mcp_tools)} MCP tools")
for tool in mcp_tools:
    logger.info(f"  - {tool.name}: {tool.description.split('\n')[0][:100]}...")


# Agent
agent = Agent(llm=llm, tools=tool_specs, mcp_config=mcp_config)

llm_messages = []  # collect raw LLM messages


def conversation_callback(event: EventBase):
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
        TextContent(text="Can you search about OpenHands V1 in my notion workspace.")
    ],
)

logger.info("Starting conversation with MCP integration...")
response = conversation.send_message(message)
conversation.run()

print("=" * 100)
print("Conversation finished. Got the following LLM messages:")
for i, message in enumerate(llm_messages):
    print(f"Message {i}: {str(message)[:200]}")
