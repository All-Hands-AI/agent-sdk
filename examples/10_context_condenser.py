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
    LLMSummarizingCondenser,
    Message,
    TextContent,
    Tool,
    get_logger,
)
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
    BashTool(working_dir=cwd),
    FileEditorTool(),
    TaskTrackerTool(save_dir=cwd),
]

# Create LLM Summarizing Condenser
# This condenser will automatically summarize conversation history when it
# exceeds max_size
condenser = LLMSummarizingCondenser(
    llm=llm,
    max_size=20,  # Trigger condensation when conversation has more than 20 events
    keep_first=4,  # Always keep the first 4 events (system prompt, initial messages)
)

# Agent with condenser
agent = Agent(llm=llm, tools=tools, condenser=condenser)

llm_messages = []  # collect raw LLM messages


def conversation_callback(event: Event):
    if isinstance(event, LLMConvertibleEvent):
        llm_messages.append(event.to_llm_message())


conversation = Conversation(agent=agent, callbacks=[conversation_callback])

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
