"""
Demo: Enhanced Bash Execution in Sandboxed Environment

This script demonstrates the improved execute_bash functionality without
requiring LLM API keys or running full agent conversations.

It shows:
1. How to use the execute_bash method
2. Complete result handling (exit codes, output)
3. Error handling for failed commands
4. Multi-line command execution
5. File operations and environment inspection

Note: This requires Docker to be running for DockerSandboxedAgentServer
"""

from openhands.sdk import get_logger
from openhands.sdk.sandbox import DockerSandboxedAgentServer


logger = get_logger(__name__)


def demo_bash_execution():
    """Demonstrate the enhanced bash execution capabilities."""

    logger.info("🚀 Starting Bash Execution Demo")

    # Start the sandboxed server
    with DockerSandboxedAgentServer(
        base_image="nikolaik/python-nodejs:python3.12-nodejs22",
        host_port=8011,  # Different port to avoid conflicts
        platform="linux/arm64",  # Change to linux/amd64 if needed
    ) as server:
        logger.info(f"✅ Sandboxed server started at: {server.base_url}")

        # Demo 1: Basic command
        logger.info("\n📝 Demo 1: Basic command execution")
        result = server.execute_bash("echo 'Hello, World!' && date")
        print(f"Command ID: {result.command_id}")
        print(f"Exit Code: {result.exit_code}")
        print(f"Output:\n{result.output}")

        # Demo 2: Command with error
        logger.info("\n❌ Demo 2: Command that fails")
        error_result = server.execute_bash("ls /this/path/does/not/exist")
        print(f"Exit Code: {error_result.exit_code}")
        print(f"Error Output:\n{error_result.output}")

        # Demo 3: Environment inspection
        logger.info("\n🔍 Demo 3: Environment inspection")
        env_result = server.execute_bash("""
            echo "=== System Information ==="
            uname -a
            echo ""
            echo "=== Python Version ==="
            python --version
            echo ""
            echo "=== Node Version ==="
            node --version
            echo ""
            echo "=== Current Directory ==="
            pwd
            echo ""
            echo "=== Directory Contents ==="
            ls -la
        """)
        print(f"Exit Code: {env_result.exit_code}")
        print(f"Environment Info:\n{env_result.output}")

        # Demo 4: File operations
        logger.info("\n📁 Demo 4: File operations")
        file_ops_result = server.execute_bash("""
            echo "Creating a test file..."
            echo "This is a test file created by the demo" > demo_file.txt
            echo "File created. Contents:"
            cat demo_file.txt
            echo ""
            echo "File info:"
            ls -la demo_file.txt
            echo ""
            echo "Cleaning up..."
            rm demo_file.txt
            echo "File deleted."
        """)
        print(f"Exit Code: {file_ops_result.exit_code}")
        print(f"File Operations:\n{file_ops_result.output}")

        # Demo 5: Python script execution
        logger.info("\n🐍 Demo 5: Python script execution")
        python_result = server.execute_bash("""
            cat > demo_script.py << 'EOF'
import json
import sys
from datetime import datetime

data = {
    "message": "Hello from Python in sandbox!",
    "timestamp": datetime.now().isoformat(),
    "python_version": sys.version,
    "platform": sys.platform
}

print(json.dumps(data, indent=2))
EOF
            python demo_script.py
            rm demo_script.py
        """)
        print(f"Exit Code: {python_result.exit_code}")
        print(f"Python Script Output:\n{python_result.output}")

        # Demo 6: Command with timeout (quick demo)
        logger.info("\n⏱️ Demo 6: Command with custom timeout")
        timeout_result = server.execute_bash(
            "sleep 2 && echo 'Completed after 2 seconds'", timeout=5
        )
        print(f"Exit Code: {timeout_result.exit_code}")
        print(f"Output: {timeout_result.output.strip()}")

        logger.info("\n✅ All demos completed successfully!")


if __name__ == "__main__":
    try:
        demo_bash_execution()
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        print(f"\n❌ Demo failed: {e}")
        print("\nMake sure Docker is running and you have the required permissions.")
