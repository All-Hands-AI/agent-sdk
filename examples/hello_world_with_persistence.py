import os

from pydantic import SecretStr

from openhands.core import (
    LLM,
    ActionBase,
    CodeActAgent,
    Conversation,
    LLMConfig,
    Message,
    ObservationBase,
    TextContent,
    Tool,
    get_logger,
)
from openhands.core.event import EventType
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
llm = LLM(config=LLMConfig(
    model="litellm_proxy/anthropic/claude-sonnet-4-20250514",
    base_url="https://llm-proxy.eval.all-hands.dev",
    api_key=SecretStr(api_key),
))

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
    # print all the actions
    if isinstance(event, ActionBase):
        logger.info(f"Found a conversation action: {event}")
    elif isinstance(event, ObservationBase):
        logger.info(f"Found a conversation observation: {event}")
    elif isinstance(event, Message):
        logger.info(f"Found a conversation message: {str(event)[:200]}...")
        llm_messages.append(event.model_dump())

conversation = Conversation(agent=agent, callbacks=[conversation_callback])

conversation.send_message(
    message=Message(
        role="user",
        content=[TextContent(text="Hello! Can you create a new Python file named hello.py that prints 'Hello, World!'?")],
    )
)
conversation.run()

print("="*100)
print("Conversation finished. Got the following LLM messages:")
for i, message in enumerate(llm_messages):
    print(f"Message {i}: {str(message)[:200]}")

# Conversation persistence
print("Serializing conversation...")
conversation.save("./conversation_data")

del conversation

# Deserialize the conversation
print("Deserializing conversation...")
conversation = Conversation.load(
    dir_path="./conversation_data",
    agent=agent,
    callbacks=[conversation_callback]
)
print("Sending message to deserialized conversation...")
conversation.send_message(
    message=Message(
        role="user",
        content=[TextContent(text="Hey what did you create?")],
    )
)
conversation.run()
