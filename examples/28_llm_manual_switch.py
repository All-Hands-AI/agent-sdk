import os
import uuid

from pydantic import SecretStr

from openhands.sdk import (
    LLM,
    Agent,
    Conversation,
    Event,
    LLMConvertibleEvent,
    LocalFileStore,
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

# Create initial LLM
initial_llm = LLM(
    service_id="agent-initial",
    model="litellm_proxy/anthropic/claude-sonnet-4-20250514",
    base_url="https://llm-proxy.eval.all-hands.dev",
    api_key=SecretStr(api_key),
)

# Create DynamicRouter with initial LLM
dynamic_router = DynamicRouter(
    service_id="dynamic-router", llms_for_routing={"primary": initial_llm}
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
file_store = LocalFileStore(f"./.conversations/{conversation_id}")

conversation = Conversation(
    agent=agent,
    callbacks=[conversation_callback],
    conversation_id=conversation_id,
    workspace=os.getcwd(),
    persistence_dir="./.conversations",
)

print(f"Starting with LLM: {dynamic_router.active_llm_identifier}")
print(f"Available LLMs: {list(dynamic_router.llms_for_routing.keys())}")

# First interaction with Claude
conversation.send_message(
    message=Message(
        role="user",
        content=[TextContent(text="Hi there!")],
    )
)
conversation.run()

print("=" * 50)
print("Adding GPT-4 dynamically and switching to it...")

# Dynamically add GPT-4 and switch to it
gpt_4 = LLM(
    service_id="gpt-4",
    model="litellm_proxy/openai/gpt-4o",
    base_url="https://llm-proxy.eval.all-hands.dev",
    api_key=SecretStr(api_key),
    temperature=0.3,
)
success = dynamic_router.switch_to_llm("gpt4", gpt_4)
print(f"GPT-4 added successfully: {success}")
print(f"Current LLM: {dynamic_router.active_llm_identifier}")
print(f"Available LLMs: {list(dynamic_router.llms_for_routing.keys())}")
print()

# Second interaction with GPT-4
conversation.send_message(
    message=Message(
        role="user",
        content=[TextContent(text="Who trained you as an LLM?")],
    )
)
conversation.run()

print("Adding a smaller model for simple tasks...")

# Add a smaller model for simple tasks
mistral_small = LLM(
    service_id="mistral_model",
    model="litellm_proxy/mistral/devstral-small-2507",
    base_url="https://llm-proxy.eval.all-hands.dev",
    api_key=SecretStr(api_key),
    temperature=0.1,
)
success = dynamic_router.switch_to_llm("mistral_model", mistral_small)
print(f"Small model added successfully: {success}")
print(f"Current LLM: {dynamic_router.active_llm_identifier}")
print(f"Available LLMs: {list(dynamic_router.llms_for_routing.keys())}")

# Third interaction with small model
conversation.send_message(
    message=Message(
        role="user",
        content=[TextContent(text="Who trained you as an LLM?")],
    )
)
conversation.run()

print("Switching back to Claude for complex reasoning...")

# Switch back to Claude for complex task
dynamic_router.switch_to_llm("primary")
print(f"Current LLM: {dynamic_router.active_llm_identifier}")

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
print(f"Available LLMs: {list(dynamic_router.llms_for_routing.keys())}")

# Continue conversation after persistence
conversation.send_message(
    message=Message(
        role="user",
        content=[TextContent(text="What did we talk about earlier?")],
    )
)
conversation.run()

print("=" * 50)
print("Removing a model...")

# Remove the small model
success = dynamic_router.remove_llm("mistral_model")
print(f"Small model removed successfully: {success}")
print(f"Current LLM: {dynamic_router.active_llm_identifier}")
print(f"Remaining LLMs: {list(dynamic_router.llms_for_routing.keys())}")

# Switch to GPT-4
dynamic_router.switch_to_llm("gpt4")
print(f"Switched to LLM: {dynamic_router.active_llm_identifier}")

# Final interaction with GPT-4
conversation.send_message(
    message=Message(
        role="user",
        content=[TextContent(text="What's the meaning of life?")],
    )
)
conversation.run()

print("=" * 100)
print("Conversation finished. Got the following LLM messages:")
for i, message in enumerate(llm_messages):
    print(f"Message {i}: {str(message)[:200]}")
