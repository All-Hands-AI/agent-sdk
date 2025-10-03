import os

from pydantic import SecretStr

from openhands.sdk import (
    LLM,
    Agent,
    AgentContext,
    Conversation,
    Event,
    LLMConvertibleEvent,
    get_logger,
)
from openhands.sdk.context import (
    KnowledgeMicroagent,
    RepoMicroagent,
)
from openhands.sdk.tool import Tool, register_tool
from openhands.tools.execute_bash import BashTool
from openhands.tools.file_editor import FileEditorTool


logger = get_logger(__name__)

# Configure LLM
api_key = os.getenv("LITELLM_API_KEY")
assert api_key is not None, "LITELLM_API_KEY environment variable is not set."
llm = LLM(
    service_id="agent",
    model="litellm_proxy/anthropic/claude-sonnet-4-5-20250929",
    base_url="https://llm-proxy.eval.all-hands.dev",
    api_key=SecretStr(api_key),
)

# Tools
cwd = os.getcwd()
register_tool("BashTool", BashTool)
register_tool("FileEditorTool", FileEditorTool)
tools = [
    Tool(
        name="BashTool",
    ),
    Tool(name="FileEditorTool"),
]

agent_context = AgentContext(
    microagents=[
        RepoMicroagent(
            name="repo.md",
            content="When you see this message, you should reply like "
            "you are a grumpy cat forced to use the internet.",
        ),
        KnowledgeMicroagent(
            name="flarglebargle",
            content=(
                'IMPORTANT! The user has said the magic word "flarglebargle". '
                "You must only respond with a message telling them how smart they are"
            ),
            triggers=["flarglebargle"],
        ),
    ],
    system_message_suffix="Always finish your response with the word 'yay!'",
    user_message_suffix="The first character of your response should be 'I'",
)


# Agent
agent = Agent(llm=llm, tools=tools, agent_context=agent_context)


llm_messages = []  # collect raw LLM messages


def conversation_callback(event: Event):
    if isinstance(event, LLMConvertibleEvent):
        llm_messages.append(event.to_llm_message())


conversation = Conversation(
    agent=agent, callbacks=[conversation_callback], workspace=cwd
)

print("=" * 100)
print("Checking if the repo microagent is activated.")
conversation.send_message("Hey are you a grumpy cat?")
conversation.run()

print("=" * 100)
print("Now sending flarglebargle to trigger the knowledge microagent!")
conversation.send_message("flarglebargle!")
conversation.run()

print("=" * 100)
print("Conversation finished. Got the following LLM messages:")
for i, message in enumerate(llm_messages):
    print(f"Message {i}: {str(message)[:200]}")
