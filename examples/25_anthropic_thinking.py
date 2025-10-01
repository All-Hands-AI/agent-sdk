"""Example demonstrating Anthropic's extended thinking feature with thinking blocks."""

import os

from pydantic import SecretStr

from openhands.sdk import (
    LLM,
    Agent,
    Conversation,
    EventBase,
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
    model="litellm_proxy/anthropic/claude-sonnet-4-5",
    base_url="https://llm-proxy.eval.all-hands.dev",
    api_key=SecretStr(api_key),
    reasoning_effort="medium",  # Enable extended thinking
    temperature=0.1,
)

# Setup agent with bash tool
register_tool("BashTool", BashTool)
agent = Agent(llm=llm, tools=[ToolSpec(name="BashTool")])


# Callback to display thinking blocks
def show_thinking(event: EventBase):
    if isinstance(event, LLMConvertibleEvent):
        message = event.to_llm_message()
        if hasattr(message, "thinking_blocks") and message.thinking_blocks:
            print(f"\n🧠 Found {len(message.thinking_blocks)} thinking blocks")
            for i, block in enumerate(message.thinking_blocks):
                if isinstance(block, RedactedThinkingBlock):
                    print(f"  Block {i + 1}: {block.data[:1000]}...")
                elif isinstance(block, ThinkingBlock):
                    print(f"  Block {i + 1}: {block.thinking[:100]}...")


conversation = Conversation(
    agent=agent, callbacks=[show_thinking], workspace=os.getcwd()
)

print("🚀 Testing Anthropic extended thinking...")
conversation.send_message(
    "Calculate compound interest for $10,000 at 5% annually, "
    "compounded quarterly for 3 years. "
    "Show your work and verify with a bash calculation."
)
conversation.run()
print("✅ Done!")
