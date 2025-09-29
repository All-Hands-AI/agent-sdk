"""OpenHands Agent SDK — Image Input Example.

This script mirrors the basic setup from ``examples/01_hello_world.py`` but adds
vision support by sending an image to the agent alongside text instructions.
"""

import os

from pydantic import SecretStr

from openhands.sdk import (
    LLM,
    Agent,
    Conversation,
    EventBase,
    ImageContent,
    LLMConvertibleEvent,
    Message,
    TextContent,
    get_logger,
)
from openhands.sdk.tool.registry import register_tool
from openhands.sdk.tool.spec import ToolSpec
from openhands.tools.execute_bash import BashTool
from openhands.tools.str_replace_editor import FileEditorTool
from openhands.tools.task_tracker import TaskTrackerTool


logger = get_logger(__name__)

# Configure LLM (vision-capable model)
api_key = os.getenv("LITELLM_API_KEY")
assert api_key is not None, "LITELLM_API_KEY environment variable is not set."
llm = LLM(
    service_id="vision-llm",
    model="litellm_proxy/anthropic/claude-sonnet-4-5-20250929",
    base_url="https://llm-proxy.eval.all-hands.dev",
    api_key=SecretStr(api_key),
)

cwd = os.getcwd()

register_tool("BashTool", BashTool)
register_tool("FileEditorTool", FileEditorTool)
register_tool("TaskTrackerTool", TaskTrackerTool)

agent = Agent(
    llm=llm,
    tools=[
        ToolSpec(name="BashTool", params={"working_dir": cwd}),
        ToolSpec(name="FileEditorTool"),
        ToolSpec(name="TaskTrackerTool", params={"save_dir": cwd}),
    ],
)

llm_messages = []  # collect raw LLM messages for inspection


def conversation_callback(event: EventBase) -> None:
    if isinstance(event, LLMConvertibleEvent):
        llm_messages.append(event.to_llm_message())


conversation = Conversation(agent=agent, callbacks=[conversation_callback])

IMAGE_URL = (
    "https://github.com/All-Hands-AI/OpenHands/raw/main/docs/static/img/logo.png"
)

conversation.send_message(
    Message(
        role="user",
        vision_enabled=True,
        content=[
            TextContent(
                text=(
                    "Study this image and describe the key elements you see. "
                    "Summarize them in a short paragraph and suggest a catchy caption."
                )
            ),
            ImageContent(image_urls=[IMAGE_URL]),
        ],
    )
)
conversation.run()

conversation.send_message(
    "Great! Please save your description and caption into image_report.md."
)
conversation.run()


print("=" * 100)
print("Conversation finished. Got the following LLM messages:")
for i, message in enumerate(llm_messages):
    print(f"Message {i}: {str(message)[:200]}")
