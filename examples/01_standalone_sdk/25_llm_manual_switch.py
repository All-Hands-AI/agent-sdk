import os
import uuid

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
from openhands.sdk.llm.router.impl.dynamic import DynamicRouter
from openhands.tools.preset.default import get_default_tools


logger = get_logger(__name__)

# Configure initial LLM
api_key = os.getenv("LLM_API_KEY")
assert api_key is not None, "LLM_API_KEY environment variable is not set."

# Create DynamicRouter with 2 initial LLMs
claude_llm = LLM(
    service_id="agent-initial",
    model="litellm_proxy/anthropic/claude-sonnet-4-5-20250929",
    base_url="https://llm-proxy.eval.all-hands.dev",
    api_key=SecretStr(api_key),
)

gpt_5_llm = LLM(
    service_id="gpt-5",
    model="litellm_proxy/openai/gpt-5-2025-08-07",
    base_url="https://llm-proxy.eval.all-hands.dev",
    api_key=SecretStr(api_key),
)

dynamic_router = DynamicRouter(
    service_id="dynamic-router",
    llms_for_routing={
        "primary": claude_llm,
        "gpt-5": gpt_5_llm,
    },  # primary is the default
)

# Tools
cwd = os.getcwd()
tools = get_default_tools()

# Agent with dynamic router
agent = Agent(llm=dynamic_router, tools=tools)

llm_messages = []  # collect raw LLM messages


def conversation_callback(event: Event):
    if isinstance(event, LLMConvertibleEvent):
        llm_messages.append(event.to_llm_message())


# Set up conversation with persistence for serialization demo
conversation_id = uuid.uuid4()

conversation = Conversation(
    agent=agent,
    callbacks=[conversation_callback],
    conversation_id=conversation_id,
    workspace=os.getcwd(),
    persistence_dir="./.conversations",
)

print(f"Starting with LLM: {dynamic_router.active_llm_identifier}")
print(f"Available LLMs: {list(dynamic_router.llms_for_routing.keys())}")

# First interaction with Claude - primary LLM
conversation.send_message(
    message=Message(
        role="user",
        content=[TextContent(text="Hi there!")],
    )
)
conversation.run()

print("=" * 50)
print("Switching to GPT-5...")

# Manually switch to GPT-5
success = dynamic_router.switch_to_llm("gpt-5")
print(f"GPT-5 switched successfully: {success}")
print(f"Current LLM: {dynamic_router.active_llm_identifier}")

# Interaction with GPT-5
conversation.send_message(
    message=Message(
        role="user",
        content=[TextContent(text="Who trained you as an LLM?")],
    )
)
conversation.run()


# Show current state before serialization
print(f"Before serialization - Current LLM: {dynamic_router.active_llm_identifier}")
print(f"Available LLMs: {list(dynamic_router.llms_for_routing.keys())}")

# Delete conversation to simulate restart
del conversation

# Recreate conversation from persistence
print("Recreating conversation from persistence...")
conversation = Conversation(
    agent=agent,
    callbacks=[conversation_callback],
    conversation_id=conversation_id,
    persistence_dir="./.conversations",
)

print(f"After deserialization - Current LLM: {dynamic_router.active_llm_identifier}")
assert dynamic_router.active_llm_identifier == "gpt-5"
print(f"Available LLMs: {list(dynamic_router.llms_for_routing.keys())}")

# Continue conversation after persistence
conversation.send_message(
    message=Message(
        role="user",
        content=[TextContent(text="What did we talk about earlier?")],
    )
)
conversation.run()

# Switch back to primary model for complex task
print("Switching back to claude for complex reasoning...")

dynamic_router.switch_to_llm("primary")
print(f"Switched to LLM: {dynamic_router.active_llm_identifier}")

conversation.send_message(
    message=Message(
        role="user",
        content=[
            TextContent(
                text="Explain the concept of dynamic programming in one sentence."
            )
        ],
    )
)
conversation.run()

print("Demonstrating persistence with LLM switching...")


print("=" * 100)
print("Conversation finished. Got the following LLM messages:")
for i, message in enumerate(llm_messages):
    print(f"Message {i}: {str(message)[:200]}")
