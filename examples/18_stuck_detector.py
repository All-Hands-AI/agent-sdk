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
tools = [
    BashTool.create(working_dir=os.getcwd()),
    FileEditorTool.create(),
]

# Agent
agent = Agent(llm=llm, tools=tools)

llm_messages = []  # collect raw LLM messages


def conversation_callback(event: Event):
    if isinstance(event, LLMConvertibleEvent):
        llm_messages.append(event.to_llm_message())


# Create conversation with built-in stuck detection
conversation = Conversation(
    agent=agent,
    callbacks=[conversation_callback],
    stuck_detection=True,
)

# Send a reasonable task
conversation.send_message(
    Message(
        role="user",
        content=[
            TextContent(
                text=(
                    "Please execute 'ls' command 5 times, each in its own "
                    "action without any thought and then exit at the 6th step."
                )
            )
        ],
    )
)

# Run the conversation - stuck detection happens automatically
conversation.run()

assert conversation.stuck_detector is not None
final_stuck_check = conversation.stuck_detector.is_stuck()
print(f"Final stuck status: {final_stuck_check}")

print("=" * 100)
print("Conversation finished. Got the following LLM messages:")
for i, message in enumerate(llm_messages):
    print(f"Message {i}: {str(message)[:200]}")
