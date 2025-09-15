"""
To manage context in long-running conversations, the agent can use a context condenser
that keeps the conversation history within a specified size limit. This example
demonstrates using the `LLMSummarizingCondenser`, which automatically summarizes
older parts of the conversation when the history exceeds a defined threshold.
"""

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
    Tool,
    get_logger,
)
from openhands.sdk.context.condenser import LLMSummarizingCondenser
from openhands.sdk.io.local import LocalFileStore
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
tools: list[Tool] = [
    BashTool.create(working_dir=cwd),
    FileEditorTool.create(),
    TaskTrackerTool.create(save_dir=cwd),
]

# Create a condenser to manage the context. The condenser will automatically truncate
# conversation history when it exceeds max_size, and replaces the dropped events with an
#  LLM-generated summary. This condenser triggers when there are more than ten events in
# the conversation history, and always keeps the first two events (system prompts,
# initial user messages) to preserve important context.
condenser = LLMSummarizingCondenser(llm=llm, max_size=10, keep_first=2)

# Agent with condenser
agent = Agent(llm=llm, tools=tools, condenser=condenser)

llm_messages = []  # collect raw LLM messages


def conversation_callback(event: Event):
    if isinstance(event, LLMConvertibleEvent):
        llm_messages.append(event.to_llm_message())


file_store = LocalFileStore("./.conversations")

conversation = Conversation(
    agent=agent, callbacks=[conversation_callback], persist_filestore=file_store
)

# Send multiple messages to demonstrate condensation
print("Sending multiple messages to demonstrate LLM Summarizing Condenser...")

conversation.send_message(
    message=Message(
        role="user",
        content=[
            TextContent(
                text=(
                    "Hello! Can you create a Python file named math_utils.py with "
                    "functions for basic arithmetic operations (add, subtract, "
                    "multiply, divide)?"
                )
            )
        ],
    )
)
conversation.run()

conversation.send_message(
    message=Message(
        role="user",
        content=[
            TextContent(
                text="Great! Now add a function to calculate the factorial of a number."
            )
        ],
    )
)
conversation.run()

conversation.send_message(
    message=Message(
        role="user",
        content=[TextContent(text="Add a function to check if a number is prime.")],
    )
)
conversation.run()

conversation.send_message(
    message=Message(
        role="user",
        content=[
            TextContent(
                text=(
                    "Add a function to calculate the greatest common divisor (GCD) "
                    "of two numbers."
                )
            )
        ],
    )
)
conversation.run()

conversation.send_message(
    message=Message(
        role="user",
        content=[
            TextContent(
                text=(
                    "Now create a test file to verify all these functions work "
                    "correctly."
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

# Conversation persistence
print("Serializing conversation...")

del conversation

# Deserialize the conversation
print("Deserializing conversation...")
conversation = Conversation(
    agent=agent, callbacks=[conversation_callback], persist_filestore=file_store
)

print("Sending message to deserialized conversation...")
conversation.send_message(
    message=Message(
        role="user",
        content=[TextContent(text="Finally, clean up by deleting both files.")],
    )
)
conversation.run()


print("=" * 100)
print("Conversation finished with LLM Summarizing Condenser.")
print(f"Total LLM messages collected: {len(llm_messages)}")
print("\nThe condenser automatically summarized older conversation history")
print("when the conversation exceeded the configured max_size threshold.")
print("This helps manage context length while preserving important information.")
