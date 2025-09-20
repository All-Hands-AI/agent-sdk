import os

from pydantic import SecretStr

from openhands.sdk import (
    LLM,
    Agent,
    Conversation,
    Message,
    TextContent,
)
from openhands.sdk.tool import ToolSpec, register_tool
from openhands.tools import BashTool, FileEditorTool


# Configure LLM
api_key = os.getenv("LITELLM_API_KEY")
assert api_key is not None, "LITELLM_API_KEY environment variable is not set."
llm = LLM(
    model="claude-sonnet-4-20250514",
    api_key=SecretStr(api_key),
)

# Tools
register_tool("BashTool", BashTool)
register_tool("FileEditorTool", FileEditorTool)
tools = [
    ToolSpec(name="BashTool", params={"working_dir": os.getcwd()}),
    ToolSpec(name="FileEditorTool", params={}),
]

# Agent
agent = Agent(llm=llm, tools=tools)
conversation = Conversation(agent)


def output_token() -> str:
    return "callable-based-secret"


conversation.update_secrets(
    {"SECRET_TOKEN": "my-secret-token-value", "SECRET_FUNCTION_TOKEN": output_token}
)

conversation.send_message(
    Message(
        role="user",
        content=[TextContent(text="just echo $SECRET_TOKEN")],
    )
)

conversation.run()

conversation.send_message(
    Message(
        role="user",
        content=[TextContent(text="just echo $SECRET_FUNCTION_TOKEN")],
    )
)

conversation.run()
