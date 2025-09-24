import os

from pydantic import SecretStr

from openhands.sdk import (
    LLM,
    Agent,
    Conversation,
    EventBase,
    LLMConvertibleEvent,
    get_logger,
)
from openhands.sdk.tool import ToolSpec, register_tool
from openhands.tools.execute_bash import BashTool
from openhands.tools.str_replace_editor import FileEditorTool


logger = get_logger(__name__)

# Configure LLM
api_key = os.getenv("LLM_API_KEY") or os.getenv("LITELLM_API_KEY")
base_url = os.getenv("LLM_BASE_URL", "https://llm-proxy.eval.all-hands.dev")
model = os.getenv("LLM_MODEL", "anthropic/claude-sonnet-4-20250514")
assert api_key is not None, (
    "LLM_API_KEY or LITELLM_API_KEY environment variable is not set."
)
llm = LLM(
    model=model,
    base_url=base_url,
    api_key=SecretStr(api_key),
)

cwd = os.getcwd()
register_tool("BashTool", BashTool)
register_tool("FileEditorTool", FileEditorTool)
tool_specs = [
    ToolSpec(name="BashTool", params={"working_dir": cwd}),
    ToolSpec(name="FileEditorTool"),
]

# Add MCP Tools
mcp_config = {"mcpServers": {"fetch": {"command": "uvx", "args": ["mcp-server-fetch"]}}}

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

logger.info("Starting conversation with MCP integration...")
conversation.send_message(
    "Read https://github.com/All-Hands-AI/OpenHands and write 3 facts "
    "about the project into FACTS.txt."
)
conversation.run()

conversation.send_message("Great! Now delete that file.")
conversation.run()

print("=" * 100)
print("Conversation finished. Got the following LLM messages:")
for i, message in enumerate(llm_messages):
    print(f"Message {i}: {str(message)[:200]}")

assert llm.metrics is not None
print(
    f"Conversation finished. Final LLM metrics with details: {llm.metrics.model_dump()}"
)
