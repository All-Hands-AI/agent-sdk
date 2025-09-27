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
    assert runtime_api_key is not None, (
        "SANDBOX_API_KEY environment variable is not set."
    )

    # 3) Get runtime API URL
    runtime_api_url = os.getenv(
        "SANDBOX_REMOTE_RUNTIME_API_URL", "https://runtime-api.eval.all-hands.dev"
    )

    llm = LLM(
        service_id="agent",
        model="litellm_proxy/anthropic/claude-sonnet-4-20250514",
        base_url="https://llm-proxy.eval.all-hands.dev",
        api_key=SecretStr(api_key),
    )

    # 4) Start the remote agent server using the runtime API
    # IMPORTANT: You need to use an image that has the OpenHands agent server built in.
    # You can either:
    # - Build one using DockerSandboxedAgentServer first and push to a registry
    # - Use a pre-built agent server image
    # - Build using the agent server Dockerfile

    # For this example, we'll assume you have built and pushed an agent server image
    # If you don't have one, you'll need to build it first:
    # 1. Use DockerSandboxedAgentServer to build locally
    # 2. Tag and push the image to a registry accessible by the runtime API

    with RemoteSandboxedAgentServer(
        api_url=runtime_api_url,
        api_key=runtime_api_key,
        base_image="your-registry/agent-server:latest",  # Replace with your image
        host_port=8010,
        session_id=f"agent-server-example-{int(time.time())}",
        resource_factor=1,  # Must be 1, 2, 4, or 8
        runtime_class="gvisor",  # or "sysbox" for more privileged access
        init_timeout=300.0,  # 5 minutes timeout for initialization
        keep_alive=False,  # Set to True to keep runtime alive after closing
        pause_on_close=False,  # Set to True to pause instead of stopping
    ) as server:
        # 5) Create agent – IMPORTANT: working_dir must be the path inside container
        agent = get_default_agent(
            llm=llm,
            working_dir="/workspace",
            cli_mode=True,
        )

        # 6) Set up callback collection, like example 22
        received_events: list = []
        last_event_time = {"ts": time.time()}

        def event_callback(event) -> None:
            event_type = type(event).__name__
            logger.info(f"🔔 Callback received event: {event_type}\n{event}")
            received_events.append(event)
            last_event_time["ts"] = time.time()

        # 7) Create RemoteConversation and do the same 2-step task
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
                "Create a simple Python script that prints "
                "'Hello from remote sandbox!' and save it as hello_remote.py. "
                "Then run it."
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
            conversation.send_message(
                "Great! Now create a simple web server using Python's http.server "
                "module that serves a 'Hello World' page on port 8080. Show me the "
                "command to start it but don't actually start it."
            )
            conversation.run()
            logger.info("✅ Second task completed!")
        finally:
            print("\n🧹 Cleaning up conversation...")
            conversation.close()


if __name__ == "__main__":
    main()
