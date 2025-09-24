import os

from pydantic import SecretStr

from openhands.sdk import (
    LLM,
    Agent,
    Conversation,
    EventBase,
    ImageContent,
    LLMConvertibleEvent,
    Message,
    TextContent,
    get_logger,
)
from openhands.sdk.llm.router import MultimodalRouter
from openhands.sdk.preset.default import get_default_tools


logger = get_logger(__name__)

# Configure LLM
api_key = os.getenv("LLM_API_KEY") or os.getenv("LITELLM_API_KEY")
base_url = os.getenv("LLM_BASE_URL", "https://llm-proxy.eval.all-hands.dev")
primary_model = os.getenv("LLM_MODEL", "anthropic/claude-sonnet-4-20250514")
secondary_model = os.getenv("LLM_SECONDARY_MODEL", "mistral/devstral-small-2507")
assert api_key is not None, (
    "LLM_API_KEY or LITELLM_API_KEY environment variable is not set."
)

primary_llm = LLM(
    model=primary_model,
    base_url=base_url,
    api_key=SecretStr(api_key),
)
secondary_llm = LLM(
    model=secondary_model,
    base_url=base_url,
    api_key=SecretStr(api_key),
)
multimodal_router = MultimodalRouter(
    llms_for_routing={"primary": primary_llm, "secondary": secondary_llm},
)

# Tools
cwd = os.getcwd()
tools = get_default_tools(working_dir=cwd)  # Use our default openhands experience

# Agent
agent = Agent(llm=multimodal_router, tools=tools)

llm_messages = []  # collect raw LLM messages


def conversation_callback(event: EventBase):
    if isinstance(event, LLMConvertibleEvent):
        llm_messages.append(event.to_llm_message())


conversation = Conversation(agent=agent, callbacks=[conversation_callback])

conversation.send_message(
    message=Message(
        role="user",
        content=[TextContent(text=("Hi there, who trained you?"))],
    )
)
conversation.run()

conversation.send_message(
    message=Message(
        role="user",
        content=[
            ImageContent(
                image_urls=["http://images.cocodataset.org/val2017/000000039769.jpg"]
            ),
            TextContent(text=("What do you see in the image above?")),
        ],
    )
)
conversation.run()

conversation.send_message(
    message=Message(
        role="user",
        content=[TextContent(text=("Who trained you as an LLM?"))],
    )
)
conversation.run()


print("=" * 100)
print("Conversation finished. Got the following LLM messages:")
for i, message in enumerate(llm_messages):
    print(f"Message {i}: {str(message)[:200]}")
