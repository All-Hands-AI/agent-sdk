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
    get_logger,
)
from openhands.tools import BashTool, FileEditorTool
from openhands.tools.browser_use import (
    BrowserToolExecutor,
    browser_get_state_tool,
    browser_navigate_tool,
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
browser_executor = BrowserToolExecutor(headless=False)
browser_navigate_tool = browser_navigate_tool.set_executor(browser_executor)
browser_get_state_tool = browser_get_state_tool.set_executor(browser_executor)
tools = [
    BashTool.create(working_dir=cwd),
    FileEditorTool.create(),
    browser_navigate_tool,
    browser_get_state_tool,
]

# Agent
agent = Agent(llm=llm, tools=tools)

llm_messages = []  # collect raw LLM messages


def conversation_callback(event: Event):
    if isinstance(event, LLMConvertibleEvent):
        llm_messages.append(event.to_llm_message())


conversation = Conversation(agent=agent, callbacks=[conversation_callback])

conversation.send_message(
    message=Message(
        role="user",
        content=[
            TextContent(
                text=(
                    "Hello! Could you find the number 1 post on Show HN using browser?"
                )
            )
        ],
    )
)
conversation.run()


print("=" * 100)
print("Conversation finished. Got the following LLM messages:")
for i, message in enumerate(llm_messages):
    print(f"Message {i}: {str(message)[:200]}")
