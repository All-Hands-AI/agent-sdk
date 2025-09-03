"""Bash-related tests ported from OpenHands runtime test_bash.py.

This file contains tests ported from the original OpenHands runtime test_bash.py,
adapted to work with the SDK's BashSession implementation.
"""

import os
import sys
import tempfile
import time

import pytest

from openhands.sdk.logger import get_logger
from openhands.tools.execute_bash.bash_session import BashSession
from openhands.tools.execute_bash.definition import ExecuteBashAction


logger = get_logger(__name__)


# Helper function to determine if running on Windows
def is_windows():
    return sys.platform == "win32"


def _run_bash_action(session: BashSession, command: str, **kwargs):
    """Helper function to execute a bash command and return the observation."""
    action = ExecuteBashAction(command=command, security_risk="LOW", **kwargs)
    obs = session.execute(action)
    logger.info(f"Command: {command}")
    logger.info(f"Output: {obs.output}")
    logger.info(f"Exit code: {obs.metadata.exit_code}")
    return obs


@pytest.mark.skipif(is_windows(), reason="Test uses Linux-specific HTTP server")
def test_bash_server():
    """Test running a server with timeout and interrupt."""
    with tempfile.TemporaryDirectory() as temp_dir:
        session = BashSession(work_dir=temp_dir, no_change_timeout_seconds=1)
        session.initialize()
        try:
            # Use python -u for unbuffered output, potentially helping
            # capture initial output on Windows
            obs = _run_bash_action(
                session, "python -u -m http.server 8081", timeout=1.0
            )
            assert obs.metadata.exit_code == -1
            assert "Serving HTTP on" in obs.output

            # Send Ctrl+C to interrupt
            obs = _run_bash_action(session, "C-c", is_input=True)
            assert obs.metadata.exit_code in (1, 130)  # Common interrupt exit codes
            assert "CTRL+C was sent" in obs.metadata.suffix

            # Verify we can run commands after interrupt
            obs = _run_bash_action(session, "ls")
            assert obs.metadata.exit_code == 0

            # Run server again to verify it works
            obs = _run_bash_action(
                session, "python -u -m http.server 8081", timeout=1.0
            )
            assert obs.metadata.exit_code == -1
            assert "Serving HTTP on" in obs.output

        finally:
            session.close()


@pytest.mark.skipif(
    is_windows(), reason="Test uses Linux-specific background processes"
)
def test_bash_background_server():
    """Test running a server in background."""
    with tempfile.TemporaryDirectory() as temp_dir:
        session = BashSession(work_dir=temp_dir)
        session.initialize()
        server_port = 8081
        try:
            # Start the server in background
            obs = _run_bash_action(session, f"python3 -m http.server {server_port} &")
            assert obs.metadata.exit_code == 0

            # Give the server a moment to be ready
            time.sleep(1)

            # Verify the server is running by curling it
            obs = _run_bash_action(session, f"curl http://localhost:{server_port}")
            assert obs.metadata.exit_code == 0
            # Check for content typical of python http.server directory listing
            assert "Directory listing for" in obs.output

            # Kill the server
            obs = _run_bash_action(session, 'pkill -f "http.server"')
            assert obs.metadata.exit_code == 0

        finally:
            session.close()


def test_multiline_commands():
    """Test multiline command execution."""
    with tempfile.TemporaryDirectory() as temp_dir:
        session = BashSession(work_dir=temp_dir)
        session.initialize()
        try:
            if is_windows():
                # Windows PowerShell version using backticks for line continuation
                obs = _run_bash_action(session, 'Write-Output `\n "foo"')
                assert obs.metadata.exit_code == 0
                assert "foo" in obs.output

                # test multiline output
                obs = _run_bash_action(session, 'Write-Output "hello`nworld"')
                assert obs.metadata.exit_code == 0
                assert "hello\nworld" in obs.output

                # test whitespace
                obs = _run_bash_action(session, 'Write-Output "a`n`n`nz"')
                assert obs.metadata.exit_code == 0
                assert "\n\n\n" in obs.output
            else:
                # Original Linux bash version
                # single multiline command
                obs = _run_bash_action(session, 'echo \\\n -e "foo"')
                assert obs.metadata.exit_code == 0
                assert "foo" in obs.output

                # test multiline echo
                obs = _run_bash_action(session, 'echo -e "hello\nworld"')
                assert obs.metadata.exit_code == 0
                assert "hello\nworld" in obs.output

                # test whitespace
                obs = _run_bash_action(session, 'echo -e "a\\n\\n\\nz"')
                assert obs.metadata.exit_code == 0
                assert "\n\n\n" in obs.output
        finally:
            session.close()


@pytest.mark.skipif(
    is_windows(), reason="Test relies on Linux bash-specific complex commands"
)
def test_complex_commands():
    """Test complex bash command execution."""
    cmd = (
        'count=0; tries=0; while [ $count -lt 3 ]; do result=$(echo "Heads"); '
        'tries=$((tries+1)); echo "Flip $tries: $result"; '
        'if [ "$result" = "Heads" ]; then count=$((count+1)); else count=0; fi; '
        'done; echo "Got 3 heads in a row after $tries flips!";'
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        session = BashSession(work_dir=temp_dir)
        session.initialize()
        try:
            obs = _run_bash_action(session, cmd)
            assert obs.metadata.exit_code == 0
            assert "Got 3 heads in a row after 3 flips!" in obs.output
        finally:
            session.close()


def test_no_ps2_in_output():
    """Test that the PS2 sign is not added to the output of a multiline command."""
    with tempfile.TemporaryDirectory() as temp_dir:
        session = BashSession(work_dir=temp_dir)
        session.initialize()
        try:
            if is_windows():
                obs = _run_bash_action(session, 'Write-Output "hello`nworld"')
            else:
                obs = _run_bash_action(session, 'echo -e "hello\nworld"')
            assert obs.metadata.exit_code == 0

            assert "hello\nworld" in obs.output
            assert ">" not in obs.output
        finally:
            session.close()


@pytest.mark.skipif(
    is_windows(), reason="Test uses Linux-specific bash loops and sed commands"
)
def test_multiline_command_loop():
    """Test multiline command with loops."""
    # https://github.com/All-Hands-AI/OpenHands/issues/3143
    init_cmd = """mkdir -p _modules && \\
for month in {01..04}; do
    for day in {01..05}; do
        touch "_modules/2024-${month}-${day}-sample.md"
    done
done && echo "created files"
"""
    follow_up_cmd = """for file in _modules/*.md; do
    new_date=$(echo $file | sed -E \\
        's/2024-(01|02|03|04)-/2024-/;s/2024-01/2024-08/;s/2024-02/2024-09/;s/2024-03/2024-10/;s/2024-04/2024-11/')
    mv "$file" "$new_date"
done && echo "success"
"""
    with tempfile.TemporaryDirectory() as temp_dir:
        session = BashSession(work_dir=temp_dir)
        session.initialize()
        try:
            obs = _run_bash_action(session, init_cmd)
            assert obs.metadata.exit_code == 0
            assert "created files" in obs.output

            obs = _run_bash_action(session, follow_up_cmd)
            assert obs.metadata.exit_code == 0
            assert "success" in obs.output
        finally:
            session.close()


def test_multiple_multiline_commands():
    """Test that multiple commands separated by newlines are rejected."""
    with tempfile.TemporaryDirectory() as temp_dir:
        session = BashSession(work_dir=temp_dir)
        session.initialize()
        try:
            if is_windows():
                cmds = [
                    "Get-ChildItem",
                    'Write-Output "hello`nworld"',
                    """Write-Output "hello it's me\"""",
                    """Write-Output `
    ('hello ' + `
    'world')""",
                    """Write-Output 'hello\nworld\nare\nyou\nthere?'""",
                    """Write-Output 'hello\nworld\nare\nyou\n\nthere?'""",
                    """Write-Output 'hello\nworld "'""",
                ]
            else:
                cmds = [
                    "ls -l",
                    'echo -e "hello\nworld"',
                    """echo -e "hello it's me\"""",
                    """echo \\
    -e 'hello' \\
    world""",
                    """echo -e 'hello\\nworld\\nare\\nyou\\nthere?'""",
                    """echo -e 'hello\nworld\nare\nyou\n\nthere?'""",
                    """echo -e 'hello\nworld "'""",
                ]
            joined_cmds = "\n".join(cmds)

            # First test that running multiple commands at once fails
            obs = _run_bash_action(session, joined_cmds)
            assert obs.error is True
            assert "Cannot execute multiple commands at once" in obs.output

            # Now run each command individually and verify they work
            results = []
            for cmd in cmds:
                obs = _run_bash_action(session, cmd)
                assert obs.metadata.exit_code == 0
                results.append(obs.output)

            # Verify all expected outputs are present
            if is_windows():
                # Get-ChildItem should execute successfully
                # (no specific content check needed)
                pass  # results[0] contains directory listing output
            else:
                assert "total 0" in results[0]  # ls -l
            assert "hello\nworld" in results[1]  # echo -e "hello\nworld"
            assert "hello it's me" in results[2]  # echo -e "hello it\'s me"
            assert "hello world" in results[3]  # echo -e 'hello' world
            assert (
                "hello\nworld\nare\nyou\nthere?" in results[4]
            )  # echo -e 'hello\nworld\nare\nyou\nthere?'
            assert (
                "hello\nworld\nare\nyou\n\nthere?" in results[5]
            )  # echo -e with literal newlines
            assert 'hello\nworld "' in results[6]  # echo -e with quote
        finally:
            session.close()


def test_cmd_run():
    """Test basic command execution."""
    with tempfile.TemporaryDirectory() as temp_dir:
        session = BashSession(work_dir=temp_dir)
        session.initialize()
        try:
            if is_windows():
                # Windows PowerShell version
                obs = _run_bash_action(session, f"Get-ChildItem -Path {temp_dir}")
                assert obs.metadata.exit_code == 0

                obs = _run_bash_action(session, "Get-ChildItem")
                assert obs.metadata.exit_code == 0

                obs = _run_bash_action(
                    session, "New-Item -ItemType Directory -Path test"
                )
                assert obs.metadata.exit_code == 0

                obs = _run_bash_action(session, "Get-ChildItem")
                assert obs.metadata.exit_code == 0
                assert "test" in obs.output

                obs = _run_bash_action(
                    session, "New-Item -ItemType File -Path test/foo.txt"
                )
                assert obs.metadata.exit_code == 0

                obs = _run_bash_action(session, "Get-ChildItem test")
                assert obs.metadata.exit_code == 0
                assert "foo.txt" in obs.output

                # clean up
                _run_bash_action(session, "Remove-Item -Recurse -Force test")
                assert obs.metadata.exit_code == 0
            else:
                # Unix version
                obs = _run_bash_action(session, f"ls -l {temp_dir}")
                assert obs.metadata.exit_code == 0

                obs = _run_bash_action(session, "ls -l")
                assert obs.metadata.exit_code == 0
                assert "total 0" in obs.output

                obs = _run_bash_action(session, "mkdir test")
                assert obs.metadata.exit_code == 0

                obs = _run_bash_action(session, "ls -l")
                assert obs.metadata.exit_code == 0
                assert "test" in obs.output

                obs = _run_bash_action(session, "touch test/foo.txt")
                assert obs.metadata.exit_code == 0

                obs = _run_bash_action(session, "ls -l test")
                assert obs.metadata.exit_code == 0
                assert "foo.txt" in obs.output

                # clean up
                _run_bash_action(session, "rm -rf test")
                assert obs.metadata.exit_code == 0
        finally:
            session.close()


def test_run_as_user_correct_home_dir():
    """Test that home directory is correct."""
    with tempfile.TemporaryDirectory() as temp_dir:
        session = BashSession(work_dir=temp_dir)
        session.initialize()
        try:
            if is_windows():
                # Windows PowerShell version
                obs = _run_bash_action(session, "cd $HOME && Get-Location")
                assert obs.metadata.exit_code == 0
                # Check for Windows-style home paths
                userprofile = os.getenv("USERPROFILE")
                home = os.getenv("HOME")
                assert (userprofile and userprofile in obs.output) or (
                    home and home in obs.output
                )
            else:
                # Original Linux version
                obs = _run_bash_action(session, "cd ~ && pwd")
                assert obs.metadata.exit_code == 0
                home = os.getenv("HOME")
                assert home and home in obs.output
        finally:
            session.close()


def test_multi_cmd_run_in_single_line():
    """Test multiple commands in a single line."""
    with tempfile.TemporaryDirectory() as temp_dir:
        session = BashSession(work_dir=temp_dir)
        session.initialize()
        try:
            if is_windows():
                # Windows PowerShell version using semicolon
                obs = _run_bash_action(session, "Get-Location && Get-ChildItem")
                assert obs.metadata.exit_code == 0
                assert temp_dir in obs.output
            else:
                # Original Linux version using &&
                obs = _run_bash_action(session, "pwd && ls -l")
                assert obs.metadata.exit_code == 0
                assert temp_dir in obs.output
                assert "total 0" in obs.output
        finally:
            session.close()


def test_stateful_cmd():
    """Test that commands maintain state across executions."""
    with tempfile.TemporaryDirectory() as temp_dir:
        session = BashSession(work_dir=temp_dir)
        session.initialize()
        try:
            if is_windows():
                # Windows PowerShell version
                obs = _run_bash_action(
                    session, "New-Item -ItemType Directory -Path test -Force"
                )
                assert obs.metadata.exit_code == 0

                obs = _run_bash_action(session, "Set-Location test")
                assert obs.metadata.exit_code == 0

                obs = _run_bash_action(session, "Get-Location")
                assert obs.metadata.exit_code == 0
                # Account for both forward and backward slashes in path
                norm_path = temp_dir.replace("\\", "/").replace("//", "/")
                test_path = f"{norm_path}/test".replace("//", "/")
                assert test_path in obs.output.replace("\\", "/")
            else:
                # Original Linux version
                obs = _run_bash_action(session, "mkdir -p test")
                assert obs.metadata.exit_code == 0

                obs = _run_bash_action(session, "cd test")
                assert obs.metadata.exit_code == 0

                obs = _run_bash_action(session, "pwd")
                assert obs.metadata.exit_code == 0
                assert f"{temp_dir}/test" in obs.output.strip()
        finally:
            session.close()


def test_failed_cmd():
    """Test failed command execution."""
    with tempfile.TemporaryDirectory() as temp_dir:
        session = BashSession(work_dir=temp_dir)
        session.initialize()
        try:
            obs = _run_bash_action(session, "non_existing_command")
            assert obs.metadata.exit_code != 0
        finally:
            session.close()


def test_python_version():
    """Test Python version command."""
    with tempfile.TemporaryDirectory() as temp_dir:
        session = BashSession(work_dir=temp_dir)
        session.initialize()
        try:
            obs = _run_bash_action(session, "python --version")
            assert obs.metadata.exit_code == 0
            assert "Python 3" in obs.output
        finally:
            session.close()


def test_pwd_property():
    """Test pwd property updates."""
    with tempfile.TemporaryDirectory() as temp_dir:
        session = BashSession(work_dir=temp_dir)
        session.initialize()
        try:
            # Create a subdirectory and verify pwd updates
            obs = _run_bash_action(session, "mkdir -p random_dir")
            assert obs.metadata.exit_code == 0

            obs = _run_bash_action(session, "cd random_dir && pwd")
            assert obs.metadata.exit_code == 0
            assert "random_dir" in obs.output
        finally:
            session.close()


def test_basic_command():
    """Test basic command execution with various scenarios."""
    with tempfile.TemporaryDirectory() as temp_dir:
        session = BashSession(work_dir=temp_dir)
        session.initialize()
        try:
            if is_windows():
                # Test simple command
                obs = _run_bash_action(session, "Write-Output 'hello world'")
                assert "hello world" in obs.output
                assert obs.metadata.exit_code == 0

                # Test command with error
                obs = _run_bash_action(session, "nonexistent_command")
                assert obs.metadata.exit_code != 0
                assert (
                    "not recognized" in obs.output or "command not found" in obs.output
                )

                # Test command with special characters
                obs = _run_bash_action(
                    session,
                    'Write-Output "hello   world    with`nspecial  chars"',
                )
                assert "hello   world    with\nspecial  chars" in obs.output
                assert obs.metadata.exit_code == 0

                # Test multiple commands in sequence
                cmd = (
                    'Write-Output "first" && Write-Output "second" && '
                    'Write-Output "third"'
                )
                obs = _run_bash_action(session, cmd)
                assert "first" in obs.output
                assert "second" in obs.output
                assert "third" in obs.output
                assert obs.metadata.exit_code == 0
            else:
                # Original Linux version
                # Test simple command
                obs = _run_bash_action(session, "echo 'hello world'")
                assert "hello world" in obs.output
                assert obs.metadata.exit_code == 0

                # Test command with error
                obs = _run_bash_action(session, "nonexistent_command")
                assert obs.metadata.exit_code == 127
                assert "nonexistent_command: command not found" in obs.output

                # Test command with special characters
                obs = _run_bash_action(
                    session, "echo 'hello   world    with\nspecial  chars'"
                )
                assert "hello   world    with\nspecial  chars" in obs.output
                assert obs.metadata.exit_code == 0

                # Test multiple commands in sequence
                obs = _run_bash_action(
                    session, 'echo "first" && echo "second" && echo "third"'
                )
                assert "first" in obs.output
                assert "second" in obs.output
                assert "third" in obs.output
                assert obs.metadata.exit_code == 0
        finally:
            session.close()


@pytest.mark.skipif(
    is_windows(), reason="Powershell does not support interactive commands"
)
def test_interactive_command():
    """Test interactive command execution."""
    with tempfile.TemporaryDirectory() as temp_dir:
        session = BashSession(work_dir=temp_dir, no_change_timeout_seconds=1)
        session.initialize()
        try:
            # Test interactive command
            obs = _run_bash_action(
                session, 'read -p "Enter name: " name && echo "Hello $name"'
            )
            # This should trigger SOFT timeout or complete immediately
            assert "Enter name:" in obs.output
            if obs.metadata.exit_code == -1:
                # Command is still running, waiting for input
                assert (
                    "[The command has no new output after 1 seconds."
                    in obs.metadata.suffix
                )
                obs = _run_bash_action(session, "John", is_input=True)
                assert "Hello John" in obs.output
                assert (
                    "[The command completed with exit code 0.]" in obs.metadata.suffix
                )
            else:
                # Command completed immediately (likely got EOF)
                # This is acceptable behavior in some environments
                pass

            # Test multiline command input with here document
            obs = _run_bash_action(
                session,
                """cat << EOF
line 1
line 2
EOF""",
            )
            assert "line 1\nline 2" in obs.output
            assert "[The command completed with exit code 0.]" in obs.metadata.suffix
            assert obs.metadata.exit_code == 0
        finally:
            session.close()


@pytest.mark.skipif(
    is_windows(),
    reason="Test relies on Linux-specific commands like seq and bash for loops",
)
def test_long_output():
    """Test long output generation."""
    with tempfile.TemporaryDirectory() as temp_dir:
        session = BashSession(work_dir=temp_dir)
        session.initialize()
        try:
            # Generate a long output
            obs = _run_bash_action(
                session, 'for i in $(seq 1 5000); do echo "Line $i"; done'
            )
            assert obs.metadata.exit_code == 0
            assert "Line 1" in obs.output
            assert "Line 5000" in obs.output
        finally:
            session.close()


@pytest.mark.skipif(
    is_windows(),
    reason="Test relies on Linux-specific commands like seq and bash for loops",
)
def test_long_output_exceed_history_limit():
    """Test long output that exceeds history limit."""
    with tempfile.TemporaryDirectory() as temp_dir:
        session = BashSession(work_dir=temp_dir)
        session.initialize()
        try:
            # Generate a long output
            obs = _run_bash_action(
                session, 'for i in $(seq 1 50000); do echo "Line $i"; done'
            )
            assert obs.metadata.exit_code == 0
            assert "Previous command outputs are truncated" in obs.metadata.prefix
            assert "Line 40000" in obs.output
            assert "Line 50000" in obs.output
        finally:
            session.close()


@pytest.mark.skipif(
    is_windows(), reason="Test uses Linux-specific temp directory and bash for loops"
)
def test_long_output_from_nested_directories():
    """Test long output from nested directory operations."""
    with tempfile.TemporaryDirectory() as temp_dir:
        session = BashSession(work_dir=temp_dir)
        session.initialize()
        try:
            # Create nested directories with many files
            setup_cmd = (
                "mkdir -p /tmp/test_dir && cd /tmp/test_dir && "
                'for i in $(seq 1 100); do mkdir -p "folder_$i"; '
                'for j in $(seq 1 100); do touch "folder_$i/file_$j.txt"; done; done'
            )
            obs = _run_bash_action(session, setup_cmd.strip(), timeout=60)
            assert obs.metadata.exit_code == 0

            # List the directory structure recursively
            obs = _run_bash_action(session, "ls -R /tmp/test_dir", timeout=60)
            assert obs.metadata.exit_code == 0

            # Verify output contains expected files
            assert "folder_1" in obs.output
            assert "file_1.txt" in obs.output
            assert "folder_100" in obs.output
            assert "file_100.txt" in obs.output
        finally:
            session.close()


@pytest.mark.skipif(
    is_windows(),
    reason="Test uses Linux-specific commands like find and grep with complex syntax",
)
def test_command_backslash():
    """Test command with backslash escaping."""
    with tempfile.TemporaryDirectory() as temp_dir:
        session = BashSession(work_dir=temp_dir)
        session.initialize()
        try:
            # Create a file with the content "implemented_function"
            cmd = (
                "mkdir -p /tmp/test_dir && "
                'echo "implemented_function" > /tmp/test_dir/file_1.txt'
            )
            obs = _run_bash_action(session, cmd)
            assert obs.metadata.exit_code == 0

            # Test correct escaping of \;
            cmd = (
                'find /tmp/test_dir -type f -exec grep -l "implemented_function" {} \\;'
            )
            obs = _run_bash_action(session, cmd)
            assert obs.metadata.exit_code == 0
            assert "/tmp/test_dir/file_1.txt" in obs.output
        finally:
            session.close()


def test_command_output_continuation():
    """Test command output continuation for long-running commands."""
    with tempfile.TemporaryDirectory() as temp_dir:
        session = BashSession(work_dir=temp_dir, no_change_timeout_seconds=3)
        session.initialize()
        try:
            if is_windows():
                # Windows PowerShell version
                obs = _run_bash_action(
                    session,
                    "1..5 | ForEach-Object { Write-Output $_; Start-Sleep 3 }",
                    timeout=2.5,
                )
                assert obs.output.strip() == "1"
                assert obs.metadata.prefix == ""
                assert (
                    "[The command timed out after 2.5 seconds." in obs.metadata.suffix
                )

                # Continue watching output
                obs = _run_bash_action(session, "", timeout=2.5)
                assert (
                    "[Below is the output of the previous command.]"
                    in obs.metadata.prefix
                )
                assert obs.output.strip() == "2"
                assert (
                    "[The command timed out after 2.5 seconds." in obs.metadata.suffix
                )

                # Continue until completion
                for expected in ["3", "4", "5"]:
                    obs = _run_bash_action(session, "", timeout=2.5)
                    assert (
                        "[Below is the output of the previous command.]"
                        in obs.metadata.prefix
                    )
                    assert obs.output.strip() == expected
                    assert (
                        "[The command timed out after 2.5 seconds."
                        in obs.metadata.suffix
                    )

                # Final empty command to complete
                obs = _run_bash_action(session, "")
                assert (
                    "[The command completed with exit code 0.]" in obs.metadata.suffix
                )
            else:
                # Original Linux version
                # Start a command that produces output slowly
                obs = _run_bash_action(
                    session, "for i in {1..5}; do echo $i; sleep 3; done", timeout=2.5
                )
                assert obs.output.strip() == "1"
                assert obs.metadata.prefix == ""
                assert (
                    "[The command timed out after 2.5 seconds." in obs.metadata.suffix
                )

                # Continue watching output
                obs = _run_bash_action(session, "", timeout=2.5)
                assert (
                    "[Below is the output of the previous command.]"
                    in obs.metadata.prefix
                )
                assert obs.output.strip() == "2"
                assert (
                    "[The command timed out after 2.5 seconds." in obs.metadata.suffix
                )

                # Continue until completion
                for expected in ["3", "4", "5"]:
                    obs = _run_bash_action(session, "", timeout=2.5)
                    assert (
                        "[Below is the output of the previous command.]"
                        in obs.metadata.prefix
                    )
                    assert obs.output.strip() == expected
                    assert (
                        "[The command timed out after 2.5 seconds."
                        in obs.metadata.suffix
                    )

                # Final empty command to complete
                obs = _run_bash_action(session, "")
                assert (
                    "[The command completed with exit code 0.]" in obs.metadata.suffix
                )
        finally:
            session.close()


def test_long_running_command_follow_by_execute():
    """Test long running command followed by another execution."""
    with tempfile.TemporaryDirectory() as temp_dir:
        session = BashSession(work_dir=temp_dir, no_change_timeout_seconds=3)
        session.initialize()
        try:
            if is_windows():
                obs = _run_bash_action(
                    session,
                    "1..3 | ForEach-Object { Write-Output $_; sleep 3 }",
                    timeout=2.5,
                )
            else:
                # Test command that produces output slowly
                obs = _run_bash_action(
                    session, "for i in {1..3}; do echo $i; sleep 3; done", timeout=2.5
                )

            assert "1" in obs.output  # First number should appear before timeout
            assert obs.metadata.exit_code == -1  # -1 indicates command is still running
            assert "[The command timed out after 2.5 seconds." in obs.metadata.suffix
            assert obs.metadata.prefix == ""

            # Continue watching output
            obs = _run_bash_action(session, "", timeout=2.5)
            assert "2" in obs.output
            assert (
                obs.metadata.prefix
                == "[Below is the output of the previous command.]\n"
            )
            assert "[The command timed out after 2.5 seconds." in obs.metadata.suffix
            assert obs.metadata.exit_code == -1  # -1 indicates command is still running

            # Test command that produces no output
            obs = _run_bash_action(session, "sleep 15", timeout=2.5)
            assert "3" not in obs.output
            assert (
                obs.metadata.prefix
                == "[Below is the output of the previous command.]\n"
            )
            assert "The previous command is still running" in obs.metadata.suffix
            assert obs.metadata.exit_code == -1  # -1 indicates command is still running

            # Finally continue again
            obs = _run_bash_action(session, "")
            assert "3" in obs.output
            assert "[The command completed with exit code 0.]" in obs.metadata.suffix
        finally:
            session.close()


def test_empty_command_errors():
    """Test empty command error handling."""
    with tempfile.TemporaryDirectory() as temp_dir:
        session = BashSession(work_dir=temp_dir)
        session.initialize()
        try:
            # Test empty command without previous command
            # behavior should be the same on all platforms
            obs = _run_bash_action(session, "")
            assert obs.error is True
            assert (
                "ERROR: No previous running command to retrieve logs from."
                in obs.output
            )
        finally:
            session.close()


@pytest.mark.skipif(
    is_windows(), reason="Powershell does not support interactive commands"
)
def test_python_interactive_input():
    """Test Python interactive input."""
    with tempfile.TemporaryDirectory() as temp_dir:
        session = BashSession(work_dir=temp_dir, no_change_timeout_seconds=2)
        session.initialize()
        try:
            # Test Python program that asks for input - same for both platforms
            python_script = (
                "name = input('Enter your name: '); "
                "age = input('Enter your age: '); "
                "print(f'Hello {name}, you are {age} years old')"
            )

            # Start Python with the interactive script
            # For both platforms we can use the same command
            obs = _run_bash_action(session, f'python -c "{python_script}"')
            assert "Enter your name:" in obs.output
            assert obs.metadata.exit_code == -1  # -1 indicates command is still running

            # Send first input (name)
            obs = _run_bash_action(session, "Alice", is_input=True)
            assert "Enter your age:" in obs.output
            assert obs.metadata.exit_code == -1

            # Send second input (age)
            obs = _run_bash_action(session, "25", is_input=True)
            assert "Hello Alice, you are 25 years old" in obs.output
            assert obs.metadata.exit_code == 0
            assert "[The command completed with exit code 0.]" in obs.metadata.suffix
        finally:
            session.close()


@pytest.mark.skipif(
    is_windows(), reason="Powershell does not support interactive commands"
)
def test_python_interactive_input_without_set_input():
    """Test Python interactive input without setting is_input flag."""
    with tempfile.TemporaryDirectory() as temp_dir:
        session = BashSession(work_dir=temp_dir, no_change_timeout_seconds=2)
        session.initialize()
        try:
            # Test Python program that asks for input
            python_script = (
                "name = input('Enter your name: '); "
                "age = input('Enter your age: '); "
                "print(f'Hello {name}, you are {age} years old')"
            )

            # Start Python with the interactive script
            obs = _run_bash_action(session, f'python -c "{python_script}"')
            assert "Enter your name:" in obs.output
            assert obs.metadata.exit_code == -1  # -1 indicates command is still running

            # Send first input (name) without is_input=True
            obs = _run_bash_action(session, "Alice", is_input=False)
            assert "Enter your age:" not in obs.output
            expected_msg = (
                'Your command "Alice" is NOT executed. '
                "The previous command is still running"
            )
            assert expected_msg in obs.metadata.suffix
            assert obs.metadata.exit_code == -1

            # Try again now with input
            obs = _run_bash_action(session, "Alice", is_input=True)
            assert "Enter your age:" in obs.output
            assert obs.metadata.exit_code == -1

            obs = _run_bash_action(session, "25", is_input=True)
            assert "Hello Alice, you are 25 years old" in obs.output
            assert obs.metadata.exit_code == 0
            assert "[The command completed with exit code 0.]" in obs.metadata.suffix
        finally:
            session.close()


def test_bash_remove_prefix():
    """Test bash command prefix removal."""
    with tempfile.TemporaryDirectory() as temp_dir:
        session = BashSession(work_dir=temp_dir)
        session.initialize()
        try:
            # create a git repo - same for both platforms
            obs = _run_bash_action(
                session,
                "git init && git remote add origin https://github.com/All-Hands-AI/OpenHands",
            )
            assert obs.metadata.exit_code == 0

            # Check git remote - same for both platforms
            obs = _run_bash_action(session, "git remote -v")
            assert obs.metadata.exit_code == 0
            assert "https://github.com/All-Hands-AI/OpenHands" in obs.output
            assert "git remote -v" not in obs.output
        finally:
            session.close()
