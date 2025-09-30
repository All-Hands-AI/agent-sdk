"""Example demonstrating Anthropic's extended thinking feature with thinking blocks.

This example shows how to use Anthropic's extended thinking feature which provides
thinking blocks that contain the model's internal reasoning process. These blocks
are preserved and can be passed back to the API for tool use scenarios.
"""

import os

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


logger = get_logger(__name__)

# Configure LLM for Anthropic Claude with extended thinking
api_key = os.getenv("LITELLM_API_KEY")
assert api_key is not None, "LITELLM_API_KEY environment variable is not set."

llm = LLM(
    service_id="agent",
    model="litellm_proxy/anthropic/claude-sonnet-4-5",
    base_url="https://llm-proxy.eval.all-hands.dev",
    api_key=SecretStr(api_key),
    # Enable extended thinking with reasoning effort
    reasoning_effort="low",  # Can be "low", "medium", or "high"
)

# Tools
cwd = os.getcwd()
register_tool("BashTool", BashTool)
tools = [
    ToolSpec(
        name="BashTool",
        params={"no_change_timeout_seconds": 3},
    )
]

# Agent
agent = Agent(llm=llm, tools=tools)

llm_messages = []  # collect raw LLM messages


def conversation_callback(event: EventBase):
    """Callback to collect LLM messages and display thinking blocks."""
    if isinstance(event, LLMConvertibleEvent):
        message = event.to_llm_message()
        llm_messages.append(message)

        # Display thinking blocks if present
        if hasattr(message, "thinking_blocks") and message.thinking_blocks:
            print(
                f"\n🧠 Thinking Blocks Found ({len(message.thinking_blocks)} blocks):"
            )
            for i, block in enumerate(message.thinking_blocks):
                print(f"  Block {i + 1}:")
                print(f"    Type: {block.type}")
                print(f"    Thinking: {block.thinking[:200]}...")
                if len(block.thinking) > 200:
                    print("    [truncated]")
                if block.signature:
                    print(f"    Signature: {block.signature[:50]}...")
                print()

        # Also check if the event itself has thinking blocks (for MessageEvent)
        if hasattr(event, "thinking_blocks"):
            thinking_blocks = getattr(event, "thinking_blocks", [])
            if thinking_blocks:
                print(
                    f"\n🧠 Event Thinking Blocks Found ({len(thinking_blocks)} blocks):"
                )
                for i, block in enumerate(thinking_blocks):
                    print(f"  Block {i + 1}:")
                    print(f"    Type: {block.type}")
                    print(f"    Thinking: {block.thinking[:200]}...")
                    if len(block.thinking) > 200:
                        print("    [truncated]")
                    if block.signature:
                        print(f"    Signature: {block.signature[:50]}...")
                    print()


conversation = Conversation(
    agent=agent, callbacks=[conversation_callback], workspace=cwd
)

print("🚀 Starting conversation with Anthropic Claude using extended thinking...")
print("This will demonstrate thinking blocks in action.\n")

# Send a complex reasoning task that will trigger extended thinking
conversation.send_message(
    "I need you to solve this step by step: Calculate the compound interest "
    "for an investment of $10,000 at 5% annual interest rate compounded "
    "quarterly for 3 years. Show your reasoning process and then use bash "
    "to verify the calculation with a simple script."
)

conversation.run()

print("\n" + "=" * 80)
print("🎯 Conversation finished. Summary of LLM messages:")
print("=" * 80)

for i, message in enumerate(llm_messages):
    print(f"\nMessage {i + 1}:")
    print(f"  Role: {message.role}")
    print(f"  Content items: {len(message.content)}")
    print(f"  Thinking blocks: {len(message.thinking_blocks)}")
    print(f"  Reasoning content: {'Yes' if message.reasoning_content else 'No'}")

    # Show thinking block details
    if message.thinking_blocks:
        print("  Thinking block details:")
        for j, block in enumerate(message.thinking_blocks):
            print(f"    Block {j + 1}: {len(block.thinking)} chars")

    # Show content preview
    content_preview = str(message)[:150]
    print(f"  Preview: {content_preview}...")

print(f"\n📊 Total messages: {len(llm_messages)}")
thinking_messages = [m for m in llm_messages if m.thinking_blocks]
print(f"📊 Messages with thinking blocks: {len(thinking_messages)}")

if thinking_messages:
    total_thinking_blocks = sum(len(m.thinking_blocks) for m in thinking_messages)
    print(f"📊 Total thinking blocks: {total_thinking_blocks}")

    print("\n🧠 Thinking blocks successfully captured and preserved!")
    print("These blocks can be passed back to the API for tool use scenarios.")
else:
    print("\n⚠️  No thinking blocks were captured.")
    print("This might be because:")
    print("  - The model didn't use extended thinking for this query")
    print("  - The reasoning_effort was too low")
    print("  - The API response format was different than expected")
