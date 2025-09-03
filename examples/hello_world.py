import os

from pydantic import SecretStr

from openhands.sdk import (
    LLM,
    Agent,
    Conversation,
    EventType,
    LLMConfig,
    LLMConvertibleEvent,
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

# Configure LLM
api_key = os.getenv("LITELLM_API_KEY")
assert api_key is not None, "LITELLM_API_KEY environment variable is not set."
llm = LLM(
    config=LLMConfig(
        model="litellm_proxy/anthropic/claude-sonnet-4-20250514",
        base_url="https://llm-proxy.eval.all-hands.dev",
        api_key=SecretStr(api_key),
    )
)

# Tools
cwd = os.getcwd()
bash = BashExecutor(working_dir=cwd)
file_editor = FileEditorExecutor()
tools: list[Tool] = [
    execute_bash_tool.set_executor(executor=bash),
    str_replace_editor_tool.set_executor(executor=file_editor),
]

# Agent
agent = Agent(llm=llm, tools=tools)

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
                text=(
                    "Hello! Can you create a new Python file named hello.py that "
                    "prints 'Hello, World!'?"
                )
            )
        ],
    )
)
conversation.run()

print("=" * 100)
print("Conversation finished. Got the following LLM messages:")
for i, message in enumerate(llm_messages):
    print(f"Message {i}: {str(message)[:200]}")
