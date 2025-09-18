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
    get_logger,
)
from openhands.tools import (
    BashTool,
)


logger = get_logger(__name__)

# Configure LLM
api_key = os.getenv("LITELLM_API_KEY")
assert api_key is not None, "LITELLM_API_KEY environment variable is not set."
llm = LLM(
    # model="litellm_proxy/gemini/gemini-2.5-pro",
    model="litellm_proxy/deepseek/deepseek-reasoner",
    base_url="https://llm-proxy.eval.all-hands.dev",
    api_key=SecretStr(api_key),
)

# Tools
cwd = os.getcwd()
tools = [
    BashTool.create(working_dir=cwd, no_change_timeout_seconds=3),
]

# Agent
agent = Agent(llm=llm, tools=tools)

llm_messages = []  # collect raw LLM messages


def conversation_callback(event: EventBase):
    if isinstance(event, LLMConvertibleEvent):
        llm_messages.append(event.to_llm_message())


conversation = Conversation(agent=agent, callbacks=[conversation_callback])

conversation.send_message(
    message=Message(
        role="user",
        content=[
            TextContent(
                text=(
                    "Enter python interactive mode by directly running `python3`, "
                    "then tell me the current time, and exit python interactive mode."
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
