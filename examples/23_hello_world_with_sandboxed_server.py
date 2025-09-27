"""
Enhanced Hello World with Sandboxed Server Example

This example demonstrates:
1. Direct bash command execution with the improved execute_bash method
2. Agent conversation capabilities in a sandboxed environment
3. Verification of agent work using direct bash commands
4. Error handling and comprehensive logging

The example shows how you can:
- Execute bash commands directly and get complete results (exit code, output)
- Run agent conversations that can interact with the sandboxed environment
- Verify and inspect the agent's work using direct system commands
- Handle both successful operations and error conditions

This showcases the dual nature of the sandboxed server: it can both host
agent conversations AND provide direct programmatic access to the environment.
"""

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
from openhands.sdk.sandbox import DockerSandboxedAgentServer


logger = get_logger(__name__)


def main() -> None:
    # 1) Ensure we have LLM API key
    api_key = os.getenv("LITELLM_API_KEY")
    assert api_key is not None, "LITELLM_API_KEY environment variable is not set."

    llm = LLM(
        service_id="agent",
        model="litellm_proxy/anthropic/claude-sonnet-4-20250514",
        base_url="https://llm-proxy.eval.all-hands.dev",
        api_key=SecretStr(api_key),
    )

    # 2) Start the dev image in Docker via the SDK helper and wait for health
    #    Forward LITELLM_API_KEY into the container so remote tools can use it.
    with DockerSandboxedAgentServer(
        base_image="nikolaik/python-nodejs:python3.12-nodejs22",
        host_port=8010,
        # TODO: Change this to your platform if not linux/arm64
        platform="linux/arm64",
    ) as server:
        # 3) Create agent – IMPORTANT: working_dir must be the path inside container
        #    where we mounted the current repo.
        agent = get_default_agent(
            llm=llm,
            working_dir="/",
            cli_mode=True,
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

        try:
            # First, demonstrate direct bash execution capabilities
            logger.info("\n🔧 === DEMONSTRATING DIRECT BASH EXECUTION ===")

            # Test 1: Simple command with successful output
            logger.info("🧪 Test 1: Basic command execution")
            result = server.execute_bash(
                "echo 'Hello from sandboxed environment!' && pwd"
            )
            logger.info("✅ Command completed:")
            logger.info(f"   Command ID: {result.command_id}")
            logger.info(f"   Exit Code: {result.exit_code}")
            logger.info(f"   Output: {result.output.strip()}")

            # Test 2: Command that produces error
            logger.info("\n🧪 Test 2: Command with error")
            error_result = server.execute_bash("ls /nonexistent_directory")
            logger.info("❌ Command failed as expected:")
            logger.info(f"   Exit Code: {error_result.exit_code}")
            logger.info(f"   Output: {error_result.output.strip()}")

            # Test 3: Multi-line command with environment info
            logger.info("\n🧪 Test 3: Environment information")
            env_result = server.execute_bash("""
                echo "=== Environment Information ==="
                echo "Python version: $(python --version)"
                echo "Node version: $(node --version)"
                echo "Current directory: $(pwd)"
                echo "Available disk space:"
                df -h / | tail -1
                echo "Memory info:"
                free -h | head -2
            """)
            logger.info("📊 Environment info:")
            logger.info(f"   Exit Code: {env_result.exit_code}")
            logger.info(f"   Output:\n{env_result.output}")

            # Test 4: Create and execute a Python script
            logger.info("\n🧪 Test 4: Create and run Python script")
            script_result = server.execute_bash("""
                cat > test_script.py << 'EOF'
import sys
import os
print("Hello from Python script!")
print(f"Python version: {sys.version}")
print(f"Current working directory: {os.getcwd()}")
print("Files in current directory:")
for item in os.listdir('.'):
    print(f"  - {item}")
EOF
                python test_script.py
            """)
            logger.info("🐍 Python script execution:")
            logger.info(f"   Exit Code: {script_result.exit_code}")
            logger.info(f"   Output:\n{script_result.output}")

            # Test 5: File operations
            logger.info("\n🧪 Test 5: File operations")
            file_result = server.execute_bash("""
                echo "Creating test files..."
                echo "This is test file 1" > file1.txt
                echo "This is test file 2" > file2.txt
                echo "Files created:"
                ls -la *.txt
                echo "Content of file1.txt:"
                cat file1.txt
                echo "Cleaning up..."
                rm file1.txt file2.txt test_script.py
                echo "Cleanup complete!"
            """)
            logger.info("📁 File operations:")
            logger.info(f"   Exit Code: {file_result.exit_code}")
            logger.info(f"   Output:\n{file_result.output}")

            logger.info("\n🤖 === NOW STARTING AGENT CONVERSATION ===")
            logger.info(f"📋 Conversation ID: {conversation.state.id}")
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

            # Verify the agent's work using direct bash execution
            logger.info("\n🔍 Verifying agent's work with direct bash execution...")
            verify_result = server.execute_bash(
                "ls -la FACTS.txt && echo '--- Content of FACTS.txt ---' && "
                "cat FACTS.txt"
            )
            if verify_result.exit_code == 0:
                logger.info("✅ Agent successfully created FACTS.txt:")
                logger.info(f"{verify_result.output}")
            else:
                logger.info("❌ FACTS.txt not found or error reading it:")
                logger.info(f"{verify_result.output}")

            logger.info("🚀 Running conversation again...")
            conversation.send_message("Great! Now delete that file.")
            conversation.run()
            logger.info("✅ Second task completed!")

            # Verify deletion using direct bash execution
            logger.info("\n🔍 Verifying file deletion...")
            delete_verify_result = server.execute_bash(
                "ls -la FACTS.txt 2>&1 || echo 'File successfully deleted'"
            )
            logger.info("🗑️ Deletion verification:")
            logger.info(f"   Exit Code: {delete_verify_result.exit_code}")
            logger.info(f"   Output: {delete_verify_result.output.strip()}")

        finally:
            print("\n🧹 Cleaning up conversation...")
            conversation.close()


if __name__ == "__main__":
    main()
