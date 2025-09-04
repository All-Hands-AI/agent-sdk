#!/usr/bin/env python3
"""
Demo script showing the new terminal session architecture and auto-detection.

This example demonstrates:
1. Auto-detection of the best available terminal session type
2. Manual selection of specific session types
3. Cross-platform compatibility (tmux, subprocess, PowerShell)
4. Soft timeout and stateful terminal features
"""

import os
import tempfile

from openhands.tools.execute_bash import BashTool
from openhands.tools.execute_bash.definition import ExecuteBashAction


def demo_auto_detection():
    """Demonstrate auto-detection of terminal session type."""
    print("=== Auto-Detection Demo ===")

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create BashTool with auto-detection (default behavior)
        tool = BashTool(working_dir=temp_dir)

        session_type = type(tool.executor.session).__name__
        print(f"Auto-detected session type: {session_type}")

        # Test basic functionality
        action = ExecuteBashAction(
            command="echo 'Hello from auto-detected session!'", security_risk="LOW"
        )
        obs = tool.executor(action)
        print(f"Output: {obs.output.strip()}")
        print(f"Exit code: {obs.metadata.exit_code}")
        print()


def demo_forced_session_types():
    """Demonstrate forcing specific session types."""
    print("=== Forced Session Types Demo ===")

    with tempfile.TemporaryDirectory() as temp_dir:
        # Test subprocess session (always available)
        print("Testing SubprocessBashSession:")
        tool = BashTool(working_dir=temp_dir, session_type="subprocess")
        session_type = type(tool.executor.session).__name__
        print(f"Forced session type: {session_type}")

        action = ExecuteBashAction(
            command="echo 'Hello from subprocess session!'", security_risk="LOW"
        )
        obs = tool.executor(action)
        print(f"Output: {obs.output.strip()}")
        print()

        # Test tmux session (if available)
        try:
            print("Testing TmuxBashSession:")
            tool = BashTool(working_dir=temp_dir, session_type="tmux")
            session_type = type(tool.executor.session).__name__
            print(f"Forced session type: {session_type}")

            action = ExecuteBashAction(
                command="echo 'Hello from tmux session!'", security_risk="LOW"
            )
            obs = tool.executor(action)
            print(f"Output: {obs.output.strip()}")
            print()
        except RuntimeError as e:
            print(f"Tmux not available: {e}")
            print()

        # Test PowerShell session (if available)
        try:
            print("Testing PowershellSession:")
            tool = BashTool(working_dir=temp_dir, session_type="powershell")
            session_type = type(tool.executor.session).__name__
            print(f"Forced session type: {session_type}")

            action = ExecuteBashAction(
                command="Write-Host 'Hello from PowerShell session!'",
                security_risk="LOW",
            )
            obs = tool.executor(action)
            print(f"Output: {obs.output.strip()}")
            print()
        except RuntimeError as e:
            print(f"PowerShell not available: {e}")
            print()


def demo_stateful_terminal():
    """Demonstrate stateful terminal features."""
    print("=== Stateful Terminal Demo ===")

    with tempfile.TemporaryDirectory() as temp_dir:
        tool = BashTool(working_dir=temp_dir)
        session_type = type(tool.executor.session).__name__
        print(f"Using session type: {session_type}")

        # Create a test file
        action = ExecuteBashAction(
            command="echo 'test content' > test.txt", security_risk="LOW"
        )
        obs = tool.executor(action)
        print(f"Created test file: exit code {obs.metadata.exit_code}")

        # Change directory (should persist)
        subdir = os.path.join(temp_dir, "subdir")
        os.makedirs(subdir)
        action = ExecuteBashAction(command=f"cd {subdir}", security_risk="LOW")
        obs = tool.executor(action)
        print(f"Changed directory: exit code {obs.metadata.exit_code}")

        # Check current directory (should be the subdirectory)
        action = ExecuteBashAction(command="pwd", security_risk="LOW")
        obs = tool.executor(action)
        print(f"Current directory: {obs.output.strip()}")

        # Set environment variable (persistence varies by session type)
        action = ExecuteBashAction(command="export TEST_VAR=hello", security_risk="LOW")
        obs = tool.executor(action)
        print(f"Set environment variable: exit code {obs.metadata.exit_code}")

        # Check environment variable
        action = ExecuteBashAction(command="echo $TEST_VAR", security_risk="LOW")
        obs = tool.executor(action)
        print(f"Environment variable value: {obs.output.strip()}")
        print()


def demo_timeout_features():
    """Demonstrate timeout features."""
    print("=== Timeout Features Demo ===")

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create tool with custom timeout settings
        tool = BashTool(
            working_dir=temp_dir,
            no_change_timeout_seconds=2,  # 2 second soft timeout
            session_type="subprocess",  # Use subprocess for consistent behavior
        )

        print("Testing soft timeout (no output change)...")
        action = ExecuteBashAction(command="sleep 5", security_risk="LOW")
        obs = tool.executor(action)

        if obs.timeout:
            print("Command timed out as expected")
            print(f"Timeout reason: {obs.metadata.suffix}")
        else:
            print("Command completed unexpectedly")

        print()

        print("Testing hard timeout...")
        action = ExecuteBashAction(command="sleep 5", timeout=1.0, security_risk="LOW")
        obs = tool.executor(action)

        if obs.timeout:
            print("Command timed out as expected")
            print(f"Timeout reason: {obs.metadata.suffix}")
        else:
            print("Command completed unexpectedly")

        print()


def main():
    """Run all demos."""
    print("Terminal Session Architecture Demo")
    print("=" * 50)
    print()

    demo_auto_detection()
    demo_forced_session_types()
    demo_stateful_terminal()
    demo_timeout_features()

    print("Demo completed!")


if __name__ == "__main__":
    main()
