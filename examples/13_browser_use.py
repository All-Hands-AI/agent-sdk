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
    browser_click_tool,
    browser_close_tab_tool,
    browser_get_content_tool,
    browser_get_state_tool,
    browser_go_back_tool,
    browser_list_tabs_tool,
    browser_navigate_tool,
    browser_scroll_tool,
    browser_switch_tab_tool,
    browser_type_tool,
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
browser_executor = BrowserToolExecutor()
browser_use_tools = [
    browser_navigate_tool.set_executor(browser_executor),
    browser_click_tool.set_executor(browser_executor),
    browser_get_state_tool.set_executor(browser_executor),
    browser_get_content_tool.set_executor(browser_executor),
    browser_type_tool.set_executor(browser_executor),
    browser_scroll_tool.set_executor(browser_executor),
    browser_go_back_tool.set_executor(browser_executor),
    browser_list_tabs_tool.set_executor(browser_executor),
    browser_switch_tab_tool.set_executor(browser_executor),
    browser_close_tab_tool.set_executor(browser_executor),
]

tools = [BashTool.create(working_dir=cwd), FileEditorTool.create(), *browser_use_tools]

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
                    "Could you go to https://all-hands.dev/ blog page and "
                    "summarize main points of the latest blog?"
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
