"""
Example: Hello World with Remote Sandboxed Agent

This example demonstrates how to use the RemoteSandboxedAgentServer to run
an agent in a remote sandboxed environment using the OpenHands Runtime API.

The RemoteSandboxedAgentServer provides:
- Remote execution environment via Runtime API
- Automatic session management and authentication
- Health monitoring and error handling
- File upload/download capabilities
- Bash command execution

Prerequisites:
- Runtime API key (set SANDBOX_API_KEY environment variable)
- Access to OpenHands Runtime API endpoint

Usage:
    export SANDBOX_API_KEY="your-api-key-here"
    python examples/25_hello_world_with_remote_sandboxed_agent.py
"""

import os
import time

from pydantic import SecretStr

from openhands.sdk import (
    LLM,
    get_logger,
)
from openhands.sdk.conversation.impl.remote_conversation import RemoteConversation
from openhands.sdk.preset.default import get_default_agent
from openhands.sdk.sandbox import RemoteSandboxedAgentServer


logger = get_logger(__name__)


def main() -> None:
    # 1) Ensure we have LLM API key
    llm_api_key = os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    if not llm_api_key:
        raise ValueError(
            "Please set OPENAI_API_KEY or ANTHROPIC_API_KEY environment variable"
        )

    # 2) Ensure we have Runtime API key
    runtime_api_key = os.getenv("SANDBOX_API_KEY")
    if not runtime_api_key:
        raise ValueError(
            "Please set SANDBOX_API_KEY environment variable with your "
            "Runtime API key.\n"
            "You can get one from your OpenHands Runtime API provider."
        )

    # 3) Configure LLM
    llm = LLM(
        model="gpt-4o-mini",  # or "claude-3-5-sonnet-20241022"
        api_key=SecretStr(llm_api_key),
        service_id="remote-sandboxed-example",
    )

    # 4) Get default agent
    working_dir = "/workspace"  # Working directory in the remote environment
    agent = get_default_agent(
        llm=llm,
        working_dir=working_dir,
    )

    # 5) Configure remote sandboxed agent server
    runtime_api_url = os.getenv(
        "RUNTIME_API_URL",
        "https://runtime-api.example.com",  # Replace with actual API URL
    )

    base_image = "python:3.12"  # Base container image for the remote environment

    logger.info("Starting remote sandboxed agent server...")
    logger.info(f"Runtime API URL: {runtime_api_url}")
    logger.info(f"Base image: {base_image}")

    # 6) Start the remote sandboxed agent server
    try:
        with RemoteSandboxedAgentServer(
            api_url=runtime_api_url,
            api_key=runtime_api_key,
            base_image=base_image,
            host_port=8010,  # Local port to expose the agent server
        ) as server:
            logger.info(f"Remote sandboxed agent server started at: {server.base_url}")

            # 7) Server is now running and ready
            logger.info("Server is ready for connections")

            # 8) Create conversation using the remote server
            conversation = RemoteConversation(
                agent=agent,
                host=server.base_url,
            )

            # 9) Send a simple message
            logger.info("Sending message to agent...")
            response = conversation.send_message(
                "Hello! Can you help me write a simple Python script that "
                "prints 'Hello, World!'?"
            )

            logger.info("Agent response:")
            logger.info(response)

            # 10) Demonstrate file operations (if supported)
            try:
                # Test bash execution
                logger.info("Testing bash execution...")
                result = server.execute_bash(
                    "echo 'Testing remote execution' && python --version"
                )
                logger.info("Bash execution result:")
                logger.info(f"  Command ID: {result.command_id}")
                logger.info(f"  Exit Code: {result.exit_code}")
                logger.info(f"  Output: {result.output}")

                # Test a command that produces an error
                logger.info("Testing bash execution with error...")
                error_result = server.execute_bash("ls /nonexistent_directory")
                logger.info("Error command result:")
                logger.info(f"  Exit Code: {error_result.exit_code}")
                logger.info(f"  Output: {error_result.output}")

                # Test file upload
                logger.info("Testing file upload...")
                test_content = "print('Hello from uploaded file!')\n"
                server.upload_file_content(test_content, "test_script.py")
                logger.info("File uploaded successfully")

                # Test file download
                logger.info("Testing file download...")
                downloaded_content = server.download_file("test_script.py")
                if downloaded_content:
                    logger.info(f"Downloaded content: {downloaded_content.decode()}")
                else:
                    logger.info("No content downloaded")

            except Exception as e:
                logger.warning(f"File operations not fully supported: {e}")

            # 11) Keep the conversation alive for a bit
            logger.info(
                "Remote sandboxed agent server is running. You can interact with it..."
            )
            time.sleep(2)

    except Exception as e:
        logger.error(f"Failed to start remote sandboxed agent server: {e}")
        logger.error("Please check:")
        logger.error("1. SANDBOX_API_KEY is set correctly")
        logger.error("2. Runtime API URL is accessible")
        logger.error("3. Your API key has sufficient permissions")
        raise


if __name__ == "__main__":
    main()
