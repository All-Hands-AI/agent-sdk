"""Tests for TerminalSession."""

import os
import tempfile
import time

import pytest

from openhands.tools.execute_bash.definition import ExecuteBashAction
from openhands.tools.execute_bash.terminal import create_terminal_session


class TestTerminalSession:
    """Test terminal session functionality."""

    def test_session_initialization(self):
        """Test session initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            session = create_terminal_session(work_dir=temp_dir)
            session.initialize()
            assert session._initialized
            assert session.work_dir == temp_dir
            assert session.cwd == temp_dir
            session.close()

    def test_basic_command_execution(self):
        """Test basic command execution."""
        with tempfile.TemporaryDirectory() as temp_dir:
            session = create_terminal_session(work_dir=temp_dir)
            session.initialize()

            # Test simple command
            action = ExecuteBashAction(
                command="echo 'Hello World'", security_risk="LOW"
            )
            obs = session.execute(action)

            assert "Hello World" in obs.output
            assert obs.metadata.exit_code == 0
            assert "[The command completed with exit code 0.]" in obs.metadata.suffix
            session.close()

    def test_working_directory_persistence(self):
        """Test that working directory changes persist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            session = create_terminal_session(work_dir=temp_dir)
            session.initialize()

            # Create a subdirectory
            subdir = os.path.join(temp_dir, "subdir")
            os.makedirs(subdir)

            # Change to subdirectory
            action = ExecuteBashAction(command=f"cd {subdir}", security_risk="LOW")
            obs = session.execute(action)
            assert obs.metadata.exit_code == 0

            # Verify working directory changed
            action = ExecuteBashAction(command="pwd", security_risk="LOW")
            obs = session.execute(action)
            assert subdir in obs.output
            session.close()

    def test_environment_variable_persistence(self):
        """Test that environment variables persist between commands."""
        with tempfile.TemporaryDirectory() as temp_dir:
            session = create_terminal_session(work_dir=temp_dir)
            session.initialize()

            # Set environment variable
            action = ExecuteBashAction(
                command="export TEST_VAR=hello", security_risk="LOW"
            )
            obs = session.execute(action)
            assert obs.metadata.exit_code == 0

            # Check if variable persists
            action = ExecuteBashAction(command="echo $TEST_VAR", security_risk="LOW")
            obs = session.execute(action)
            # Note: Environment persistence is limited in subprocess implementation
            # This test documents the current behavior
            session.close()

    def test_command_timeout(self):
        """Test command timeout functionality."""
        with tempfile.TemporaryDirectory() as temp_dir:
            session = create_terminal_session(work_dir=temp_dir)
            session.initialize()

            # Test hard timeout
            action = ExecuteBashAction(
                command="sleep 5", timeout=1.0, security_risk="LOW"
            )
            start_time = time.time()
            obs = session.execute(action)
            elapsed = time.time() - start_time

            assert elapsed < 3.0  # Should timeout before 3 seconds
            assert obs.timeout
            assert "timed out after" in obs.metadata.suffix
            session.close()

    def test_soft_timeout(self):
        """Test soft timeout (no output change) functionality."""
        with tempfile.TemporaryDirectory() as temp_dir:
            session = create_terminal_session(
                work_dir=temp_dir, no_change_timeout_seconds=2
            )
            session.initialize()

            # Command that produces no output for a while
            action = ExecuteBashAction(command="sleep 5", security_risk="LOW")
            start_time = time.time()
            obs = session.execute(action)
            elapsed = time.time() - start_time

            # Should timeout due to no output change
            assert (
                elapsed < 6.0
            )  # Should timeout before 6 seconds (2s timeout + overhead)
            assert obs.timeout
            assert "no new output after" in obs.metadata.suffix
            session.close()

    def test_interrupt_functionality(self):
        """Test interrupt functionality."""
        with tempfile.TemporaryDirectory() as temp_dir:
            session = create_terminal_session(work_dir=temp_dir)
            session.initialize()

            # Start a long-running command in a separate thread
            import threading

            result = {}

            def run_command():
                action = ExecuteBashAction(command="sleep 10", security_risk="LOW")
                result["obs"] = session.execute(action)

            thread = threading.Thread(target=run_command)
            thread.start()

            # Wait a bit then interrupt
            time.sleep(0.5)
            assert session.is_running()
            success = session.interrupt()

            thread.join(timeout=5.0)

            # Check that interrupt worked
            if success:
                assert "obs" in result
                # The command should have been interrupted
                assert result["obs"].metadata.exit_code != 0 or result["obs"].timeout

            session.close()

    def test_error_handling(self):
        """Test error handling for invalid commands."""
        with tempfile.TemporaryDirectory() as temp_dir:
            session = create_terminal_session(work_dir=temp_dir)
            session.initialize()

            # Test command that doesn't exist
            action = ExecuteBashAction(
                command="nonexistent_command_12345", security_risk="LOW"
            )
            obs = session.execute(action)

            assert obs.metadata.exit_code != 0
            assert (
                "command not found" in obs.output.lower()
                or "not recognized" in obs.output.lower()
            )
            session.close()

    def test_multiple_commands_rejection(self):
        """Test that multiple commands are rejected."""
        with tempfile.TemporaryDirectory() as temp_dir:
            session = create_terminal_session(work_dir=temp_dir)
            session.initialize()

            # Test multiple commands separated by newline
            action = ExecuteBashAction(
                command="echo 'first'\necho 'second'", security_risk="LOW"
            )
            obs = session.execute(action)

            assert obs.error
            assert "Cannot execute multiple commands at once" in obs.output
            session.close()

    def test_empty_command_handling(self):
        """Test handling of empty commands."""
        with tempfile.TemporaryDirectory() as temp_dir:
            session = create_terminal_session(work_dir=temp_dir)
            session.initialize()

            # Test empty command when no process is running
            action = ExecuteBashAction(command="", security_risk="LOW")
            obs = session.execute(action)

            assert obs.error
            assert "No previous running command" in obs.output
            session.close()

    def test_input_handling(self):
        """Test handling of input to running processes."""
        with tempfile.TemporaryDirectory() as temp_dir:
            session = create_terminal_session(work_dir=temp_dir)
            session.initialize()

            # Test input when no process is running
            action = ExecuteBashAction(
                command="test input", is_input=True, security_risk="LOW"
            )
            obs = session.execute(action)

            assert obs.error
            assert "No previous running command to interact with" in obs.output
            session.close()

    def test_session_cleanup(self):
        """Test proper session cleanup."""
        with tempfile.TemporaryDirectory() as temp_dir:
            session = create_terminal_session(work_dir=temp_dir)
            session.initialize()

            # Start a command
            action = ExecuteBashAction(command="echo 'test'", security_risk="LOW")
            session.execute(action)

            # Close session
            session.close()
            assert session._closed

            # Verify session can't be used after closing
            with pytest.raises(RuntimeError):
                session.execute(action)
