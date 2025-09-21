"""Default preset configuration for OpenHands agents."""

import os

from pydantic import SecretStr

from openhands.sdk import (
    LLM,
    Agent,
    Conversation,
    EventBase,
    LLMConvertibleEvent,
    Message,
    TextContent,
    get_logger,
)
from openhands.sdk.preset.default import get_default_agent_spec


logger = get_logger(__name__)

# Configure LLM
api_key = os.getenv("LITELLM_API_KEY")
assert api_key is not None, "LITELLM_API_KEY environment variable is not set."
llm = LLM(
    model="litellm_proxy/anthropic/claude-sonnet-4-20250514",
    base_url="https://llm-proxy.eval.all-hands.dev",
    api_key=SecretStr(api_key),
)

# Tools
cwd = os.getcwd()

# Using the default agent spec preset
agent_spec = get_default_agent_spec(llm=llm, working_dir=cwd, cli_mode=True)
# Or define it explicitly like this:
# from openhands.sdk import AgentSpec, ToolSpec
# from openhands.sdk.context.condenser import LLMSummarizingCondenser
# agent_spec = AgentSpec(
#     llm=llm,
#     tools=[
#         ToolSpec(name="BashTool", params={"working_dir": cwd}),
#         ToolSpec(name="FileEditorTool", params={}),
#         ToolSpec(name="TaskTrackerTool", params={"save_dir": f"{cwd}/.openhands"}),
#     ],
#     mcp_config={
#         "mcpServers": {
#             "fetch": {"command": "uvx", "args": ["mcp-server-fetch"]},
#             "repomix": {"command": "npx", "args": ["-y", "repomix@1.4.2", "--mcp"]},
#         }
#     },
#     filter_tools_regex="^(?!repomix)(.*)|^repomix.*pack_codebase.*$",
#     system_prompt_kwargs={"cli_mode": True},
#     condenser=LLMSummarizingCondenser(llm=llm, max_size=80, keep_first=4),
# )
agent = Agent.from_spec(agent_spec)

llm_messages = []  # collect raw LLM messages


def conversation_callback(event: EventBase):
    if isinstance(event, LLMConvertibleEvent):
        llm_messages.append(event.to_llm_message())


conversation = Conversation(agent=agent, callbacks=[conversation_callback])

conversation.send_message(
    message=Message(
        role="user",
        content=[TextContent(text=("Hello! Tell me what tools you have access to."))],
    )
)
conversation.run()
