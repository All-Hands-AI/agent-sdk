import os
import time

from pydantic import SecretStr

from openhands.sdk import (
    LLM,
    Conversation,
    get_logger,
)
from openhands.sdk.conversation.impl.remote_conversation import RemoteConversation
from openhands.sdk.sandbox import DockerSandboxedAgentServer
from openhands.tools.preset.default import get_default_agent


logger = get_logger(__name__)

api_key = os.getenv("LITELLM_API_KEY")
assert api_key is not None, "LITELLM_API_KEY environment variable is not set."

llm = LLM(
    service_id="agent",
    model="litellm_proxy/anthropic/claude-sonnet-4-20250514",
    base_url="https://llm-proxy.eval.all-hands.dev",
    api_key=SecretStr(api_key),
)

with DockerSandboxedAgentServer(
    base_image="nikolaik/python-nodejs:python3.12-nodejs22",
    host_port=8010,
    # TODO: Change this to your platform if not linux/arm64
    platform="linux/arm64",
    extra_ports=True,  # expose extra ports for browser access
) as server:
    """Extra ports allows you to check localhost:8013"""
    # IMPORTANT: working_dir must be the path inside container
    #    where we mounted the current repo.
    agent = get_default_agent(
        llm=llm,
        working_dir="/workspace",
        cli_mode=False,  # CLI mode = False will enable browser tools
    )

    # 4) Set up callback collection, like example 22
    received_events: list = []
    last_event_time = {"ts": time.time()}

    def event_callback(event) -> None:
        event_type = type(event).__name__
        logger.info(f"🔔 Callback received event: {event_type}\n{event}")
        received_events.append(event)
        last_event_time["ts"] = time.time()

    # 5) Create RemoteConversation and do the same 2-step task
    conversation = Conversation(
        agent=agent,
        host=server.base_url,
        callbacks=[event_callback],
        visualize=True,
    )
    assert isinstance(conversation, RemoteConversation)

    logger.info(f"\n📋 Conversation ID: {conversation.state.id}")
    logger.info("📝 Sending first message...")
    conversation.send_message(
        "Could you go to https://all-hands.dev/ blog page and summarize main "
        "points of the latest blog?"
    )
    conversation.run()

    # Wait for user confirm to exit
    y = None
    while y != "y":
        y = input(
            "Because you've enabled extra_ports=True in DockerSandboxedAgentServer, "
            "you can open a browser tab to see the *actual* browser OpenHands is "
            " interacting with via VNC.\n\n"
            "Link: http://localhost:8012/vnc.html?autoconnect=1&resize=remote\n\n\n"
            "Press 'y' and Enter to exit and terminate the sandboxed server."
            ">> "
        )
