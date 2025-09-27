#!/usr/bin/env python3
"""
Example demonstrating bash execution and file operations with sandboxed agent servers.

This example shows how to:
1. Start a sandboxed agent server (Docker or Remote)
2. Execute bash commands in the sandboxed environment
3. Upload files to the sandboxed environment
4. Download files from the sandboxed environment
5. Upload file content directly

Run with:
    python examples/27_sandboxed_server_bash_and_files.py
"""

import tempfile
from pathlib import Path

from openhands.sdk.sandbox import DockerSandboxedAgentServer


def main():
    """Demonstrate bash execution and file operations with sandboxed servers."""
    print("🚀 Sandboxed Server Bash and File Operations Example")
    print("=" * 60)

    # Create a temporary file for testing
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("Hello from the host machine!\nThis is a test file.\n")
        temp_file_path = f.name

    # Initialize download_path for cleanup
    download_path = Path(tempfile.gettempdir()) / "downloaded_from_sandbox.txt"

    try:
        # Use Docker sandboxed server (you can also use RemoteSandboxedAgentServer)
        with DockerSandboxedAgentServer(
            host_port=8011, base_image="python:3.11"
        ) as server:
            print(f"✅ Server started at: {server.base_url}")

            # 1. Execute bash commands
            print("\n📝 Executing bash commands...")

            # Simple command
            result = server.execute_bash("echo 'Hello from sandbox!'")
            print(f"Command ID: {result.command_id}")
            print(f"Command: {result.command}")
            print(f"Is running: {result.is_running}")

            # List current directory
            result = server.execute_bash("ls -la")
            print(f"Directory listing command ID: {result.command_id}")

            # Create a directory
            result = server.execute_bash("mkdir -p test_dir")
            print(f"Created directory, command ID: {result.command_id}")

            # 2. Upload file content directly
            print("\n📤 Uploading file content...")
            content = """#!/bin/bash
echo "This is a script created from content!"
echo "Current directory: $(pwd)"
echo "Files in directory:"
ls -la
"""
            success = server.upload_file_content(content, "test_script.sh")
            print(f"Upload content success: {success}")

            # Make the script executable
            result = server.execute_bash("chmod +x test_script.sh")
            print(f"Made script executable, command ID: {result.command_id}")

            # 3. Upload a file from the host
            print("\n📤 Uploading file from host...")
            success = server.upload_file(temp_file_path, "uploaded_file.txt")
            print(f"Upload file success: {success}")

            # 4. Verify uploaded files
            print("\n🔍 Verifying uploaded files...")
            result = server.execute_bash("ls -la *.txt *.sh")
            print(f"File listing command ID: {result.command_id}")

            # Run the uploaded script
            result = server.execute_bash("./test_script.sh")
            print(f"Script execution command ID: {result.command_id}")

            # 5. Create a file in the sandbox and download it
            print("\n📝 Creating file in sandbox...")
            result = server.execute_bash(
                "echo 'This file was created in the sandbox!' > sandbox_created.txt"
            )
            print(f"File creation command ID: {result.command_id}")

            # Add more content to the file
            result = server.execute_bash(
                "echo 'Current date: $(date)' >> sandbox_created.txt"
            )
            print(f"File append command ID: {result.command_id}")

            # 6. Download the file as bytes
            print("\n📥 Downloading file as bytes...")
            file_content = server.download_file("sandbox_created.txt")
            if file_content:
                print(f"Downloaded {len(file_content)} bytes")
                print(f"Content: {file_content.decode('utf-8')}")
            else:
                print("Failed to download file")

            # 7. Download file to local path
            print("\n📥 Downloading file to local path...")
            result_content = server.download_file("uploaded_file.txt", download_path)
            if result_content is None and download_path.exists():
                print(f"File downloaded to: {download_path}")
                with open(download_path) as f:
                    print(f"Downloaded content: {f.read()}")
            else:
                print("Failed to download file to local path")

            # 8. Test error handling
            print("\n❌ Testing error handling...")

            # Try to download non-existent file
            try:
                content = server.download_file("non_existent_file.txt")
                print("Unexpected: should have failed")
            except RuntimeError as e:
                print(f"Expected error for non-existent file: {e}")

            # Try to upload non-existent file
            success = server.upload_file("/non/existent/path.txt", "test.txt")
            print(f"Upload non-existent file success (should be False): {success}")

            print("\n✅ All operations completed!")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()

    finally:
        # Clean up temporary files
        try:
            Path(temp_file_path).unlink()
            if download_path.exists():
                download_path.unlink()
        except Exception:
            pass


if __name__ == "__main__":
    main()
