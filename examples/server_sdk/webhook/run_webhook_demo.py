#!/usr/bin/env python3
"""
OpenHands Webhook Protocol Demo Script

This script demonstrates the OpenHands Webhook protocol by:
1. Starting a webhook logging server on port 8001 that logs all webhook events
2. Starting an OpenHands Agent Server on port 8000 configured to send events
   to the webhook logging server

The script manages both processes and provides a clean shutdown mechanism.
"""

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional


class ProcessManager:
    """Manages multiple subprocesses with clean shutdown."""

    def __init__(self):
        self.processes: List[subprocess.Popen] = []
        self.setup_signal_handlers()

    def setup_signal_handlers(self):
        """Set up signal handlers for clean shutdown."""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        print(f"\n🛑 Received signal {signum}, shutting down...")
        self.shutdown_all()
        sys.exit(0)

    def start_process(
        self,
        cmd: List[str],
        name: str,
        cwd: Optional[str] = None,
        env: Optional[dict] = None,
    ) -> subprocess.Popen:
        """Start a subprocess and add it to the managed processes."""
        print(f"🚀 Starting {name}...")
        print(f"   Command: {' '.join(cmd)}")
        if cwd:
            print(f"   Working directory: {cwd}")

        try:
            process = subprocess.Popen(
                cmd,
                cwd=cwd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
            )
            self.processes.append(process)
            print(f"✅ {name} started with PID {process.pid}")
            return process
        except Exception as e:
            print(f"❌ Failed to start {name}: {e}")
            raise

    def shutdown_all(self):
        """Shutdown all managed processes."""
        if not self.processes:
            return

        print("🛑 Shutting down all processes...")
        for process in self.processes:
            if process.poll() is None:  # Process is still running
                print(f"   Terminating process {process.pid}...")
                try:
                    process.terminate()
                    # Give it a moment to terminate gracefully
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    print(f"   Force killing process {process.pid}...")
                    process.kill()
                except Exception as e:
                    print(f"   Error shutting down process {process.pid}: {e}")

        self.processes.clear()
        print("✅ All processes shut down")

    def wait_for_processes(self):
        """Wait for all processes to complete or handle shutdown."""
        try:
            while self.processes:
                # Check if any process has terminated
                for process in self.processes[
                    :
                ]:  # Copy list to avoid modification issues
                    if process.poll() is not None:
                        print(f"⚠️  Process {process.pid} has terminated")
                        self.processes.remove(process)

                if not self.processes:
                    break

                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Interrupted by user")
            self.shutdown_all()


def find_python_executable() -> str:
    """Find the appropriate Python executable."""
    # Try to use the same Python executable that's running this script
    python_exe = sys.executable
    if python_exe and os.path.isfile(python_exe):
        return python_exe

    # Fallback to common Python executables
    for exe in ["python3", "python"]:
        try:
            subprocess.run([exe, "--version"], check=True, capture_output=True)
            return exe
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue

    raise RuntimeError("Could not find a suitable Python executable")


def check_dependencies():
    """Check if required dependencies are available."""
    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
    except ImportError as e:
        print(f"❌ Missing required dependency: {e}")
        print("   Please install dependencies with: uv sync")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Run OpenHands Webhook Protocol Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This script demonstrates the OpenHands webhook protocol by starting:
1. A webhook logging server on port 8001 (logs all webhook events)
2. An OpenHands Agent Server on port 8000 (configured to send events to the
   logging server)

Use Ctrl+C to stop both servers.

Examples:
  python run_webhook_demo.py                    # Use default ports
  python run_webhook_demo.py --webhook-port 9001 --agent-port 9000
        """,
    )

    parser.add_argument(
        "--webhook-port",
        type=int,
        default=8001,
        help="Port for the webhook logging server (default: 8001)",
    )
    parser.add_argument(
        "--agent-port",
        type=int,
        default=8000,
        help="Port for the OpenHands Agent Server (default: 8000)",
    )
    parser.add_argument(
        "--config",
        default="openhands_agent_server_config.json",
        help=(
            "Path to agent server config file "
            "(default: openhands_agent_server_config.json)"
        ),
    )
    parser.add_argument(
        "--session-key",
        default="test-session-key",
        help=("Session API key for webhook authentication (default: test-session-key)"),
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Log level for both servers (default: INFO)",
    )
    parser.add_argument(
        "--no-webhook-server",
        action="store_true",
        help=(
            "Skip starting the webhook logging server (useful if running separately)"
        ),
    )

    args = parser.parse_args()

    # Get the directory where this script is located
    script_dir = Path(__file__).parent.absolute()
    webhook_server_path = script_dir / "webhook_logging_server.py"
    config_path = script_dir / args.config

    # Validate files exist
    if not webhook_server_path.exists():
        print(f"❌ Webhook server script not found: {webhook_server_path}")
        sys.exit(1)

    if not config_path.exists():
        print(f"❌ Config file not found: {config_path}")
        sys.exit(1)

    # Check dependencies
    check_dependencies()

    # Find Python executable
    python_exe = find_python_executable()
    print(f"🐍 Using Python executable: {python_exe}")

    # Create process manager
    manager = ProcessManager()

    try:
        # Start webhook logging server (unless disabled)
        if not args.no_webhook_server:
            webhook_cmd = [
                python_exe,
                str(webhook_server_path),
                "--host",
                "0.0.0.0",
                "--port",
                str(args.webhook_port),
                "--session-key",
                args.session_key,
                "--log-level",
                args.log_level,
            ]
            manager.start_process(
                webhook_cmd,
                f"Webhook Logging Server (port {args.webhook_port})",
                str(script_dir),
            )

            # Give the webhook server a moment to start
            print("⏳ Waiting for webhook server to start...")
            time.sleep(2)

        # Start OpenHands Agent Server
        agent_cmd = [
            python_exe,
            "-m",
            "openhands.agent_server",
            "--host",
            "0.0.0.0",
            "--port",
            str(args.agent_port),
        ]

        # Set environment variable for config file
        env = os.environ.copy()
        env["OPENHANDS_CONFIG_FILE"] = str(config_path)

        manager.start_process(
            agent_cmd, f"OpenHands Agent Server (port {args.agent_port})", env=env
        )

        # Give the agent server a moment to start
        print("⏳ Waiting for agent server to start...")
        time.sleep(3)

        # Print status and instructions
        print("\n" + "=" * 60)
        print("🎉 OpenHands Webhook Demo is running!")
        print("=" * 60)
        if not args.no_webhook_server:
            print(f"📊 Webhook Logging Server: http://localhost:{args.webhook_port}")
            print(f"   - View logs: http://localhost:{args.webhook_port}/logs")
            print(f"   - View events: http://localhost:{args.webhook_port}/events")
            print(
                f"   - View conversations: http://localhost:{args.webhook_port}/conversations"
            )
        print(f"🤖 OpenHands Agent Server: http://localhost:{args.agent_port}")
        print(f"   - API docs: http://localhost:{args.agent_port}/docs")
        print(f"📁 Config file: {config_path}")
        print("\n💡 Tips:")
        print("   - Create conversations via the Agent Server API")
        print("   - Watch webhook events appear in the logging server")
        print("   - Use Ctrl+C to stop both servers")
        print("\n🔄 Press Ctrl+C to stop the demo...")

        # Wait for processes or user interrupt
        manager.wait_for_processes()

    except KeyboardInterrupt:
        print("\n🛑 Demo interrupted by user")
    except Exception as e:
        print(f"❌ Error running demo: {e}")
        sys.exit(1)
    finally:
        manager.shutdown_all()

    print("👋 Demo completed!")


if __name__ == "__main__":
    main()
