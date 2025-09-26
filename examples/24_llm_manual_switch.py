import os
import uuid

from pydantic import SecretStr

from openhands.sdk import (
    LLM,
    Agent,
    Conversation,
    EventBase,
    LLMConvertibleEvent,
    LocalFileStore,
    Message,
    TextContent,
    get_logger,
)
from openhands.sdk.llm.router.impl.dynamic import DynamicRouter
from openhands.sdk.preset.default import get_default_tools


logger = get_logger(__name__)

# Configure initial LLM
api_key = os.getenv("LITELLM_API_KEY")
assert api_key is not None, "LITELLM_API_KEY environment variable is not set."

# Create initial LLM
initial_llm = LLM(
    service_id="agent-initial",
    model="litellm_proxy/anthropic/claude-sonnet-4-20250514",
    base_url="https://llm-proxy.eval.all-hands.dev",
    api_key=SecretStr(api_key),
)

# Create DynamicRouter with initial LLM
dynamic_router = DynamicRouter(
    service_id="dynamic-router", llms_for_routing={"claude": initial_llm}
)

# Tools
cwd = os.getcwd()
tools = get_default_tools(working_dir=cwd)

# Agent with dynamic router
agent = Agent(llm=dynamic_router, tools=tools)

llm_messages = []  # collect raw LLM messages


def conversation_callback(event: EventBase):
    if isinstance(event, LLMConvertibleEvent):
        llm_messages.append(event.to_llm_message())


# Set up conversation with persistence for serialization demo
conversation_id = uuid.uuid4()
file_store = LocalFileStore(f"./.conversations/{conversation_id}")

conversation = Conversation(
    agent=agent,
    callbacks=[conversation_callback],
    persist_filestore=file_store,
    conversation_id=conversation_id,
)

print(f"Starting with LLM: {dynamic_router.get_current_llm_name()}")
print(f"Available LLMs: {list(dynamic_router.get_available_llms().keys())}")

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
success = dynamic_router.switch_to_llm(
    "gpt4",
    model="litellm_proxy/openai/gpt-4o",
    base_url="https://llm-proxy.eval.all-hands.dev",
    api_key=api_key,
    temperature=0.3,
)
print(f"GPT-4 added successfully: {success}")
print(f"Current LLM: {dynamic_router.get_current_llm_name()}")
print(f"Available LLMs: {list(dynamic_router.get_available_llms().keys())}")
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
success = dynamic_router.switch_to_llm(
    "small_model",
    model="litellm_proxy/mistral/devstral-small-2507",
    base_url="https://llm-proxy.eval.all-hands.dev",
    api_key=api_key,
    temperature=0.1,
)
print(f"Small model added successfully: {success}")
print(f"Current LLM: {dynamic_router.get_current_llm_name()}")
print(f"Available LLMs: {list(dynamic_router.get_available_llms().keys())}")

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
dynamic_router.switch_to_llm("claude")
print(f"Current LLM: {dynamic_router.get_current_llm_name()}")

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
print(f"Before serialization - Current LLM: {dynamic_router.get_current_llm_name()}")
print(f"Available LLMs: {list(dynamic_router.get_available_llms().keys())}")

# Delete conversation to simulate restart
del conversation

# Recreate conversation from persistence
print("Recreating conversation from persistence...")
conversation = Conversation(
    agent=agent,
    callbacks=[conversation_callback],
    persist_filestore=file_store,
    conversation_id=conversation_id,
)

print(f"After deserialization - Current LLM: {dynamic_router.get_current_llm_name()}")
print(f"Available LLMs: {list(dynamic_router.get_available_llms().keys())}")

# Continue conversation after persistence
conversation.send_message(
    message=Message(
        role="user",
        content=[TextContent(text="Do you remember our previous conversation?")],
    )
)
conversation.run()

print("=" * 50)
print("Removing a model...")

# Remove the small model
success = dynamic_router.remove_llm("small_model")
print(f"Small model removed successfully: {success}")
print(f"Current LLM: {dynamic_router.get_current_llm_name()}")
print(f"Remaining LLMs: {list(dynamic_router.get_available_llms().keys())}")

print("=" * 100)
print("Conversation finished. Got the following LLM messages:")
for i, message in enumerate(llm_messages):
    print(f"Message {i}: {str(message)[:200]}")

print("\n=== Summary ===")
print("This example demonstrated:")
print("1. Creating a DynamicRouter with an initial LLM")
print("2. Dynamically adding new LLMs during conversation")
print("3. Switching between different LLMs for different tasks")
print("4. Persistence and deserialization of dynamic LLM configurations")
print("5. Removing LLMs from the router")
print("6. All LLM switches are preserved across conversation restarts")
