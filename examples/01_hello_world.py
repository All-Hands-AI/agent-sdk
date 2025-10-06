import os

from pydantic import SecretStr

from openhands.sdk import (
    LLM,
    Conversation,
    Event,
    LLMConvertibleEvent,
    get_logger,
)
from openhands.tools.preset.default import get_default_agent


logger = get_logger(__name__)

# Configure LLM
api_key = os.getenv("LITELLM_API_KEY")
assert api_key is not None, "LITELLM_API_KEY environment variable is not set."
llm = LLM(
    model="litellm_proxy/anthropic/claude-sonnet-4-5-20250929",
    base_url="https://llm-proxy.eval.all-hands.dev",
    api_key=SecretStr(api_key),
    service_id="agent",
    drop_params=True,
)

cwd = os.getcwd()
agent = get_default_agent(
    llm=llm,
    # CLI mode will disable any browser tools
    # which requires dependency like playwright that may not be
    # available in all environments.
    cli_mode=True,
)
# # Alternatively, you can manually register tools and provide Tools to Agent.
# from openhands.sdk import Agent
# from openhands.sdk.tool.registry import register_tool
# from openhands.sdk.tool.spec import Tool
# from openhands.tools.execute_bash import BashTool
# from openhands.tools.file_editor import FileEditorTool
# from openhands.tools.task_tracker import TaskTrackerTool
# register_tool("BashTool", BashTool)
# register_tool("FileEditorTool", FileEditorTool)
# register_tool("TaskTrackerTool", TaskTrackerTool)

# # Provide Tool so Agent can lazily materialize tools at runtime.
# agent = Agent(
#     llm=llm,
#     tools=[
#         Tool(name="BashTool"),
#         Tool(name="FileEditorTool"),
#         Tool(name="TaskTrackerTool"),
#     ],
# )

llm_messages = []  # collect raw LLM messages


def conversation_callback(event: Event):
    if isinstance(event, LLMConvertibleEvent):
        llm_messages.append(event.to_llm_message())


conversation = Conversation(
    agent=agent,
    callbacks=[conversation_callback],
    workspace=cwd,
)

conversation.send_message(
    "Read the current repo and write 3 facts about the project into FACTS.txt."
)
title = conversation.generate_title(max_length=60)
logger.info(f"Generated conversation title: {title}")
conversation.run()

conversation.send_message("Great! Now delete that file.")
conversation.run()


print("=" * 100)
print("Conversation finished. Got the following LLM messages:")
for i, message in enumerate(llm_messages):
    print(f"Message {i}: {str(message)[:200]}")
