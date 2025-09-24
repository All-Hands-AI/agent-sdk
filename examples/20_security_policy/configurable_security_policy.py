"""Example demonstrating configurable security policy support."""

import os
from pathlib import Path

from pydantic import SecretStr

from openhands.sdk import (
    LLM,
    Agent,
    Conversation,
    EventBase,
    LLMConvertibleEvent,
    get_logger,
)
from openhands.sdk.tool import ToolSpec, register_tool
from openhands.tools.execute_bash import BashTool
from openhands.tools.str_replace_editor import FileEditorTool


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
register_tool("BashTool", BashTool)
register_tool("FileEditorTool", FileEditorTool)
tools = [
    ToolSpec(name="BashTool", params={"working_dir": cwd}),
    ToolSpec(name="FileEditorTool"),
]

# Example 1: Agent with default security policy
print("Creating agent with default security policy...")
default_agent = Agent(llm=llm, tools=tools)
print(f"Default security policy: {default_agent.security_policy_filename}")

# Example 2: Agent with custom security policy
print("Creating agent with custom security policy...")
example_dir = Path(__file__).parent
custom_policy_path = example_dir / "custom_policy.j2"

if custom_policy_path.exists():
    custom_agent = Agent(
        llm=llm,
        tools=tools,
        security_policy_filename="custom_policy.j2",
    )
    print(f"Custom security policy: {custom_agent.security_policy_filename}")
else:
    print("Custom policy template not found, using default agent")
    custom_agent = default_agent

llm_messages = []  # collect raw LLM messages


def conversation_callback(event: EventBase):
    if isinstance(event, LLMConvertibleEvent):
        llm_messages.append(event.to_llm_message())


conversation = Conversation(agent=custom_agent, callbacks=[conversation_callback])

conversation.send_message(
    "Please create a simple Python script that reads a file. "
    "Make sure to follow security best practices."
)
conversation.run()

print("=" * 100)
print("Conversation finished. Got the following LLM messages:")
for i, message in enumerate(llm_messages):
    print(f"Message {i}: {str(message)[:200]}")
