import os

from pydantic import SecretStr

from openhands.sdk import (
    LLM,
    Agent,
    Conversation,
)
from openhands.sdk.conversation.secret_source import SecretSource
from openhands.sdk.tool import Tool, register_tool
from openhands.tools.execute_bash import BashTool
from openhands.tools.str_replace_editor import FileEditorTool


# Configure LLM
api_key = os.getenv("LITELLM_API_KEY")
assert api_key is not None, "LITELLM_API_KEY environment variable is not set."
llm = LLM(
    service_id="agent",
    model="claude-sonnet-4-20250514",
    api_key=SecretStr(api_key),
)

# Tools
register_tool("BashTool", BashTool)
register_tool("FileEditorTool", FileEditorTool)
tools = [
    Tool(name="BashTool"),
    Tool(name="FileEditorTool"),
]

# Agent
agent = Agent(llm=llm, tools=tools)
conversation = Conversation(agent)


class MySecretSource(SecretSource):
    def get_value(self) -> str:
        return "callable-based-secret"


conversation.update_secrets(
    {"SECRET_TOKEN": "my-secret-token-value", "SECRET_FUNCTION_TOKEN": MySecretSource()}
)

conversation.send_message("just echo $SECRET_TOKEN")

conversation.run()

conversation.send_message("just echo $SECRET_FUNCTION_TOKEN")

conversation.run()
