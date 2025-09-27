#!/usr/bin/env python3
"""
Example: Build and Use Remote Agent Server

This example demonstrates how to:
1. Build an agent server image locally
2. Push it to a registry (optional)
3. Use it with RemoteSandboxedAgentServer

Prerequisites:
- Docker installed and running
- Access to a Docker registry (for pushing)
- Runtime API credentials
"""

import os
import time

from openhands.sdk.conversation import Conversation
from openhands.sdk.llm.llm import LLM
from openhands.sdk.preset.default import get_default_agent
from openhands.sdk.sandbox import (
    RemoteSandboxedAgentServer,
    build_and_push_agent_server_image,
    get_agent_server_build_instructions,
)


def main():
    print("🏗️  Building and Using Remote Agent Server")
    print("=" * 50)

    # Step 1: Show build instructions
    print("\n📖 Build Instructions:")
    print(get_agent_server_build_instructions())

    # Step 2: Check if we should build an image
    build_image = (
        input("\n🤔 Do you want to build an agent server image? (y/N): ")
        .lower()
        .startswith("y")
    )

    if build_image:
        print("\n🏗️  Building agent server image...")

        # Get registry information
        registry = input(
            "Enter your Docker registry (e.g., ghcr.io/your-org): "
        ).strip()
        if not registry:
            print("❌ Registry is required for remote usage")
            return

        image_name = (
            input("Enter image name [agent-server]: ").strip() or "agent-server"
        )
        tag = input("Enter tag [latest]: ").strip() or "latest"

        push_image = input("Push to registry? (y/N): ").lower().startswith("y")

        try:
            # Build (and optionally push) the image
            full_image_name = build_and_push_agent_server_image(
                base_image="nikolaik/python-nodejs:python3.12-nodejs22",
                registry=registry,
                image_name=image_name,
                tag=tag,
                push=push_image,
            )

            print(f"✅ Image ready: {full_image_name}")

        except Exception as e:
            print(f"❌ Failed to build image: {e}")
            return
    else:
        # Use an existing image
        full_image_name = input("Enter the full image name to use: ").strip()
        if not full_image_name:
            print("❌ Image name is required")
            return

    # Step 3: Check runtime API configuration
    runtime_api_url = os.getenv("SANDBOX_REMOTE_RUNTIME_API_URL")
    runtime_api_key = os.getenv("SANDBOX_API_KEY")

    if not runtime_api_url:
        runtime_api_url = input("Enter runtime API URL: ").strip()
        if not runtime_api_url:
            print("❌ Runtime API URL is required")
            return

    if not runtime_api_key:
        runtime_api_key = input("Enter runtime API key: ").strip()
        if not runtime_api_key:
            print("❌ Runtime API key is required")
            return

    print(f"\n✅ Using runtime API: {runtime_api_url}")
    print(f"✅ Using image: {full_image_name}")

    # Step 4: Set up LLM
    llm = LLM(model="gpt-4o-mini", service_id="main")

    # Step 5: Start the remote agent server
    print("\n🚀 Starting remote agent server...")

    try:
        with RemoteSandboxedAgentServer(
            api_url=runtime_api_url,
            api_key=runtime_api_key,
            base_image=full_image_name,
            host_port=8010,
            session_id=f"build-example-{int(time.time())}",
            resource_factor=1,  # Must be 1, 2, 4, or 8
            runtime_class="gvisor",
            init_timeout=300.0,  # 5 minutes for initialization
            keep_alive=False,
            pause_on_close=False,
        ) as server:
            print("✅ Remote agent server started!")
            print(f"✅ Server URL: {server.base_url}")

            # Step 6: Create and use an agent
            agent = get_default_agent(
                llm=llm,
                working_dir="/workspace",  # Path inside the container
                cli_mode=True,
            )

            print("\n🤖 Agent created! Creating conversation...")

            # Create conversation and send a simple task
            conversation = Conversation(
                agent=agent,
                host=server.base_url,
            )

            print("📝 Sending a test message...")
            conversation.send_message(
                "Hello! Can you tell me what files are in the current directory?"
            )
            conversation.run()

            print("\n✅ Example completed successfully!")
            conversation.close()

    except Exception as e:
        print(f"❌ Error running remote agent server: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
