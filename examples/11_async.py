"""
This example demonstrates usage of a Conversation in an async context
(e.g.: From a fastapi server). The conversation is run in a background
thread and a callback with results is executed in the main runloop
"""

import asyncio
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
from openhands.sdk.conversation.types import ConversationCallbackType
from openhands.sdk.utils.async_utils import AsyncCallbackWrapper
from openhands.tools import BashTool, FileEditorTool, TaskTrackerTool


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
tools = [
    BashTool.create(working_dir=cwd),
    FileEditorTool.create(),
    TaskTrackerTool.create(save_dir=cwd),
]

# Agent
agent = Agent(llm=llm, tools=tools)

llm_messages = []  # collect raw LLM messages


# Callback coroutine
async def callback_coro(event: EventBase):
    if isinstance(event, LLMConvertibleEvent):
        llm_messages.append(event.to_llm_message())


# Synchronous run conversation
def run_conversation(callback: ConversationCallbackType):
    conversation = Conversation(agent=agent, callbacks=[callback])

    conversation.send_message(
        message=Message(
            role="user",
            content=[
                TextContent(
                    text=(
                        "Hello! Can you create a new Python file named hello.py"
                        " that prints 'Hello, World!'? Use task tracker to plan"
                        " your steps."
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


async def main():
    loop = asyncio.get_running_loop()

    # Create the callback
    callback = AsyncCallbackWrapper(callback_coro, loop)

    # Run the conversation in a background thread and wait for it to finish...
    await loop.run_in_executor(None, run_conversation, callback)

    print("=" * 100)
    print("Conversation finished. Got the following LLM messages:")
    for i, message in enumerate(llm_messages):
        print(f"Message {i}: {str(message)[:200]}")


if __name__ == "__main__":
    asyncio.run(main())
