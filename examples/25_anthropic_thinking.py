"""Example demonstrating Anthropic's extended thinking feature with thinking blocks."""

import os

from pydantic import SecretStr

from openhands.sdk import (
    LLM,
    Agent,
    Conversation,
    Event,
    LLMConvertibleEvent,
    RedactedThinkingBlock,
    ThinkingBlock,
)
from openhands.sdk.tool import ToolSpec, register_tool
from openhands.tools.execute_bash import BashTool


# Configure LLM for Anthropic Claude with extended thinking
api_key = os.getenv("LITELLM_API_KEY")
assert api_key is not None, "LITELLM_API_KEY environment variable is not set."

llm = LLM(
    service_id="agent",
    model="litellm_proxy/anthropic/claude-sonnet-4-5-20250929",
    base_url="https://llm-proxy.eval.all-hands.dev",
    api_key=SecretStr(api_key),
)

# Setup agent with bash tool
register_tool("BashTool", BashTool)
agent = Agent(llm=llm, tools=[ToolSpec(name="BashTool")])


# Callback to display thinking blocks
def show_thinking(event: Event):
    if isinstance(event, LLMConvertibleEvent):
        message = event.to_llm_message()
        if hasattr(message, "thinking_blocks") and message.thinking_blocks:
            print(f"\n🧠 Found {len(message.thinking_blocks)} thinking blocks")
            for i, block in enumerate(message.thinking_blocks):
                if isinstance(block, RedactedThinkingBlock):
                    print(f"  Block {i + 1}: {block.data}")
                elif isinstance(block, ThinkingBlock):
                    print(f"  Block {i + 1}: {block.thinking}")


conversation = Conversation(
    agent=agent, callbacks=[show_thinking], workspace=os.getcwd()
)

conversation.send_message(
    "Calculate compound interest for $10,000 at 5% annually, "
    "compounded quarterly for 3 years. Show your work.",
)
conversation.run()

conversation.send_message(
    "Now, write that number to RESULTs.txt.",
)
conversation.run()
print("✅ Done!")
