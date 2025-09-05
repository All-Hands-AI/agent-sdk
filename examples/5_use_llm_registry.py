import os

from pydantic import SecretStr

from openhands.sdk import (
    LLM,
    Agent,
    Conversation,
    EventType,
    LLMConvertibleEvent,
    LLMRegistry,
    Message,
    TextContent,
    Tool,
    get_logger,
)
from openhands.tools import (
    BashTool,
    FileEditorTool,
)


logger = get_logger(__name__)

# Configure LLM using LLMRegistry
api_key = os.getenv("LITELLM_API_KEY")
assert api_key is not None, "LITELLM_API_KEY environment variable is not set."

# Create LLM instance
main_llm = LLM(
    model="litellm_proxy/anthropic/claude-sonnet-4-20250514",
    base_url="https://llm-proxy.eval.all-hands.dev",
    api_key=SecretStr(api_key),
)

# Create LLM registry and add the LLM
llm_registry = LLMRegistry()
llm_registry.add("main_agent", main_llm)

# Get LLM from registry
llm = llm_registry.get("main_agent")

# Tools
cwd = os.getcwd()
tools: list[Tool] = [
    BashTool(working_dir=cwd),
    FileEditorTool(),
]

# Agent
agent = Agent(llm=llm, tools=tools)

llm_messages = []  # collect raw LLM messages


def conversation_callback(event: EventType):
    if isinstance(event, LLMConvertibleEvent):
        llm_messages.append(event.to_llm_message())


conversation = Conversation(agent=agent, callbacks=[conversation_callback])

conversation.send_message(
    message=Message(
        role="user",
        content=[
            TextContent(
                text="Hello! Can you create a new Python file named "
                "hello_registry.py that prints 'Hello from LLM Registry!'?"
            )
        ],
    )
)
conversation.run()

print("=" * 100)
print("Conversation finished. Got the following LLM messages:")
for i, message in enumerate(llm_messages):
    print(f"Message {i}: {str(message)[:200]}")

print("=" * 100)
print(f"LLM Registry services: {llm_registry.list_services()}")

# Demonstrate getting the same LLM instance from registry
same_llm = llm_registry.get("main_agent")
print(f"Same LLM instance: {llm is same_llm}")

# Demonstrate requesting a completion directly from registry
completion_response = llm_registry.request_extraneous_completion(
    service_id="completion_service",
    llm_config=main_llm,
    messages=[{"role": "user", "content": "Say hello in one word."}],
)
print(f"Direct completion response: {completion_response}")
