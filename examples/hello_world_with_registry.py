import os

from pydantic import SecretStr

from openhands.core import (
    CodeActAgent,
    Conversation,
    EventType,
    LLMConfig,
    LLMConvertibleEvent,
    LLMRegistry,
    Message,
    TextContent,
    Tool,
    get_logger,
)
from openhands.tools import (
    BashExecutor,
    FileEditorExecutor,
    execute_bash_tool,
    str_replace_editor_tool,
)


logger = get_logger(__name__)

# Configure LLM using LLMRegistry
api_key = os.getenv("LITELLM_API_KEY")
assert api_key is not None, "LITELLM_API_KEY environment variable is not set."

# Create LLM registry
llm_registry = LLMRegistry()

# Get LLM from registry (this will create and cache the LLM)
llm_config = LLMConfig(
    model="litellm_proxy/anthropic/claude-sonnet-4-20250514",
    base_url="https://llm-proxy.eval.all-hands.dev",
    api_key=SecretStr(api_key),
)
llm = llm_registry.get_llm(service_id="main_agent", config=llm_config)

# Tools
cwd = os.getcwd()
bash = BashExecutor(working_dir=cwd)
file_editor = FileEditorExecutor()
tools: list[Tool] = [
    execute_bash_tool.set_executor(executor=bash),
    str_replace_editor_tool.set_executor(executor=file_editor),
]

# Agent
agent = CodeActAgent(llm=llm, tools=tools)

llm_messages = []  # collect raw LLM messages


def conversation_callback(event: EventType):
    logger.info(f"Found a conversation message: {str(event)[:200]}...")
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
same_llm = llm_registry.get_llm(service_id="main_agent", config=llm_config)
print(f"Same LLM instance: {llm is same_llm}")

# Demonstrate requesting a completion directly from registry
completion_response = llm_registry.request_extraneous_completion(
    service_id="completion_service",
    llm_config=llm_config,
    messages=[{"role": "user", "content": "Say hello in one word."}],
)
print(f"Direct completion response: {completion_response}")
