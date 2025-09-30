import os

from pydantic import SecretStr

from openhands.sdk import (
    LLM,
    Conversation,
    EventBase,
    LLMConvertibleEvent,
    get_logger,
)
from openhands.tools.preset.default import get_default_agent


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

agent = get_default_agent(llm=llm)

llm_messages = []


def conversation_callback(event: EventBase):
    if isinstance(event, LLMConvertibleEvent):
        llm_messages.append(event.to_llm_message())


# Create conversation with built-in stuck detection
conversation = Conversation(
    agent=agent,
    callbacks=[conversation_callback],
    workspace=os.getcwd(),
    # This is by default True, shown here for clarity of the example
    stuck_detection=True,
)

# Send a task that will be caught by stuck detection
conversation.send_message(
    "Please execute 'ls' command 5 times, each in its own "
    "action without any thought and then exit at the 6th step."
)

# Run the conversation - stuck detection happens automatically
conversation.run()

assert conversation.stuck_detector is not None
final_stuck_check = conversation.stuck_detector.is_stuck()
print(f"Final stuck status: {final_stuck_check}")

print("=" * 100)
print("Conversation finished. Got the following LLM messages:")
for i, message in enumerate(llm_messages):
    print(f"Message {i}: {str(message)[:200]}")
