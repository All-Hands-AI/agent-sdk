import os
import time

from pydantic import SecretStr

from openhands.sdk import (
    LLM,
    Conversation,
    get_logger,
)
from openhands.sdk.conversation.impl.remote_conversation import RemoteConversation
from openhands.sdk.preset.default import get_default_agent
from openhands.sdk.sandbox import RemoteSandboxedAgentServer


logger = get_logger(__name__)


def main() -> None:
    # 1) Ensure we have LLM API key
    api_key = os.getenv("LITELLM_API_KEY")
    assert api_key is not None, "LITELLM_API_KEY environment variable is not set."

    # 2) Ensure we have Runtime API key
    runtime_api_key = os.getenv("SANDBOX_API_KEY")
    if runtime_api_key is None:
        runtime_api_key = input("Please enter your Runtime API key: ").strip()
        if not runtime_api_key:
            raise ValueError("Runtime API key is required")

    llm = LLM(
        service_id="agent",
        model="litellm_proxy/anthropic/claude-sonnet-4-20250514",
        base_url="https://llm-proxy.eval.all-hands.dev",
        api_key=SecretStr(api_key),
    )

    # 3) Start the remote agent server using the runtime API
    with RemoteSandboxedAgentServer(
        api_url="https://runtime-api.all-hands.dev",
        api_key=runtime_api_key,
        base_image="nikolaik/python-nodejs:python3.12-nodejs22",
        host_port=8010,
        extra_env={"LITELLM_API_KEY": api_key},
    ) as server:
        # 4) Create agent – IMPORTANT: working_dir must be the path inside container
        #    where we mounted the current repo.
        agent = get_default_agent(
            llm=llm,
            working_dir="/openhands/code",
            cli_mode=True,
        )

        # 5) Set up callback collection, like example 22
        received_events: list = []
        last_event_time = {"ts": time.time()}

        def event_callback(event) -> None:
            event_type = type(event).__name__
            logger.info(f"🔔 Callback received event: {event_type}\n{event}")
            received_events.append(event)
            last_event_time["ts"] = time.time()

        # 6) Create RemoteConversation and do the same 2-step task
        conversation = Conversation(
            agent=agent,
            host=server.base_url,
            callbacks=[event_callback],
            visualize=True,
        )
        assert isinstance(conversation, RemoteConversation)

        try:
            logger.info(f"\n📋 Conversation ID: {conversation.state.id}")
            logger.info("📝 Sending first message...")
            conversation.send_message(
                "Read the current repo and write 3 facts about the project into "
                "FACTS.txt."
            )
            logger.info("🚀 Running conversation...")
            conversation.run()
            logger.info("✅ First task completed!")
            logger.info(f"Agent status: {conversation.state.agent_status}")

            # Wait for events to settle (no events for 2 seconds)
            logger.info("⏳ Waiting for events to stop...")
            while time.time() - last_event_time["ts"] < 2.0:
                time.sleep(0.1)
            logger.info("✅ Events have stopped")

            logger.info("🚀 Running conversation again...")
            conversation.send_message("Great! Now delete that file.")
            conversation.run()
            logger.info("✅ Second task completed!")
        finally:
            print("\n🧹 Cleaning up conversation...")
            conversation.close()


if __name__ == "__main__":
    main()
