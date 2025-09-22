#!/usr/bin/env python3
"""
Script to run the web chat app example using its configuration.

This script sets up the environment and starts the OpenHands agent server
with the web chat app configuration, serving the static web files.

Usage:
    python run_web_chat_app.py
    # or
    uv run python run_web_chat_app.py
"""

import os
import subprocess
import sys
from pathlib import Path


def main():
    """Run the web chat app example."""
    # Get the script directory and project root
    script_dir = Path(__file__).parent
    web_chat_app_dir = (
        script_dir / "examples" / "server_sdk" / "webhook" / "web_chat_app"
    )
    config_file = web_chat_app_dir / "agent_server_config.json"

    # Verify the config file exists
    if not config_file.exists():
        print(f"❌ Config file not found: {config_file}")
        print("Make sure you're running this script from the agent-sdk root directory.")
        sys.exit(1)

    # Verify the web directory exists
    web_dir = web_chat_app_dir / "web"
    if not web_dir.exists():
        print(f"❌ Web directory not found: {web_dir}")
        sys.exit(1)

    # Prepare environment for the subprocess
    env = os.environ.copy()
    env["OPENHANDS_AGENT_SERVER_CONFIG_PATH"] = str(config_file)

    # Unset session API key for local development (disable authentication)
    if "SESSION_API_KEY" in env:
        del env["SESSION_API_KEY"]
        print("🔓 Disabled authentication for local development")

    print("🚀 Starting OpenHands Web Chat App")
    print(f"📁 Working directory: {web_chat_app_dir}")
    print(f"⚙️  Config file: {config_file}")
    print(f"🌐 Web files: {web_dir}")
    print("🔗 Server will be available at: http://localhost:8000")
    print("📖 API docs will be available at: http://localhost:8000/docs")
    print("🎯 Web app will be available at: http://localhost:8000/static/")
    print()

    try:
        # Start the server using uv run to ensure proper environment
        # Run from the project root to ensure proper module imports
        cmd = [
            "uv",
            "run",
            "python",
            "-m",
            "openhands.agent_server",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
            "--reload",
        ]

        print("🔧 Running command:", " ".join(cmd))
        print()

        # Run the server with the modified environment
        subprocess.run(cmd, check=True, env=env)

    except KeyboardInterrupt:
        print("\n👋 Shutting down server...")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Server failed to start: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
