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
from openhands.sdk.llm.router import RandomRouter
from openhands.sdk.preset.default import get_default_tools


logger = get_logger(__name__)

# Configure LLM
api_key = os.getenv("LITELLM_API_KEY")
assert api_key is not None, "LITELLM_API_KEY environment variable is not set."

sonnet_llm = LLM(
    model="litellm_proxy/anthropic/claude-sonnet-4-20250514",
    base_url="https://llm-proxy.eval.all-hands.dev",
    api_key=SecretStr(api_key),
)
gpt5_llm = LLM(
    model="litellm_proxy/gpt-5-2025-08-07",
    base_url="https://llm-proxy.eval.all-hands.dev",
    api_key=SecretStr(api_key),
)
random_router = RandomRouter(
    model="random-router-sonnet-gpt5",
    llms_for_routing={"sonnet": sonnet_llm, "gpt5": gpt5_llm},
)


# Tools
cwd = os.getcwd()
tools = get_default_tools(working_dir=cwd)  # Use our default openhands experience

# Agent
agent = Agent(llm=random_router, tools=tools)

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
                    "Read the current repo and "
                    "write 3 facts about the project into FACTS.txt."
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
