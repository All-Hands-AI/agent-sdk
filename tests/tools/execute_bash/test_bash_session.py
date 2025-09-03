import os
import tempfile
import time

from openhands.core.logger import get_logger
from openhands.tools.execute_bash.bash_session import (
    BashCommandStatus,
    BashSession,
)
from openhands.tools.execute_bash.definition import ExecuteBashAction

from .conftest import get_no_change_timeout_suffix


logger = get_logger(__name__)


def test_session_initialization():
    # Test with custom working directory
    with tempfile.TemporaryDirectory() as temp_dir:
        session = BashSession(work_dir=temp_dir)
        session.initialize()
        obs = session.execute(ExecuteBashAction(command="pwd", security_risk="LOW"))

        assert temp_dir in obs.output
        assert "[The command completed with exit code 0.]" in obs.metadata.suffix
        session.close()

    # Test with custom username
    session = BashSession(work_dir=os.getcwd(), username="nobody")
    session.initialize()
    assert (
        session.session.name is not None and "openhands-nobody" in session.session.name
    )
    session.close()


def test_cwd_property(tmp_path):
    session = BashSession(work_dir=tmp_path)
    session.initialize()
    # Change directory and verify pwd updates
    random_dir = tmp_path / "random"
    random_dir.mkdir()
    session.execute(ExecuteBashAction(command=f"cd {random_dir}", security_risk="LOW"))
    assert session.cwd == str(random_dir)
    session.close()


def test_basic_command():
    session = BashSession(work_dir=os.getcwd())
    session.initialize()

    # Test simple command
    obs = session.execute(
        ExecuteBashAction(command="echo 'hello world'", security_risk="LOW")
    )

    assert "hello world" in obs.output
    assert obs.metadata.suffix == "\n[The command completed with exit code 0.]"
    assert obs.metadata.prefix == ""
    assert obs.metadata.exit_code == 0
    assert session.prev_status == BashCommandStatus.COMPLETED

    # Test command with error
    obs = session.execute(
        ExecuteBashAction(command="nonexistent_command", security_risk="LOW")
    )

    assert obs.metadata.exit_code == 127
    assert "nonexistent_command: command not found" in obs.output
    assert obs.metadata.suffix == "\n[The command completed with exit code 127.]"
    assert obs.metadata.prefix == ""
    assert session.prev_status == BashCommandStatus.COMPLETED

    # Test multiple commands in sequence
    obs = session.execute(
        ExecuteBashAction(
            command='echo "first" && echo "second" && echo "third"', security_risk="LOW"
        )
    )
    assert "first" in obs.output
    assert "second" in obs.output
    assert "third" in obs.output
    assert obs.metadata.suffix == "\n[The command completed with exit code 0.]"
    assert obs.metadata.prefix == ""
    assert obs.metadata.exit_code == 0
    assert session.prev_status == BashCommandStatus.COMPLETED

    session.close()


def test_long_running_command_follow_by_execute():
    session = BashSession(work_dir=os.getcwd(), no_change_timeout_seconds=2)
    session.initialize()

    # Test command that produces output slowly
    obs = session.execute(
        ExecuteBashAction(
            command="echo 1; sleep 3; echo 2; sleep 3; echo 3", security_risk="LOW"
        )
    )

    assert "1" in obs.output  # First number should appear before timeout
    assert obs.metadata.exit_code == -1  # -1 indicates command is still running
    assert session.prev_status == BashCommandStatus.NO_CHANGE_TIMEOUT
    assert obs.metadata.suffix == get_no_change_timeout_suffix(2)
    assert obs.metadata.prefix == ""

    # Continue watching output
    obs = session.execute(
        ExecuteBashAction(command="", is_input=True, security_risk="LOW")
    )

    assert "2" in obs.output
    assert obs.metadata.prefix == "[Below is the output of the previous command.]\n"
    assert obs.metadata.suffix == get_no_change_timeout_suffix(2)
    assert obs.metadata.exit_code == -1  # -1 indicates command is still running
    assert session.prev_status == BashCommandStatus.NO_CHANGE_TIMEOUT

    # Test command that produces no output
    obs = session.execute(ExecuteBashAction(command="sleep 15", security_risk="LOW"))

    assert "3" not in obs.output
    assert obs.metadata.prefix == "[Below is the output of the previous command.]\n"
    assert "The previous command is still running" in obs.metadata.suffix
    assert obs.metadata.exit_code == -1  # -1 indicates command is still running
    assert session.prev_status == BashCommandStatus.NO_CHANGE_TIMEOUT

    time.sleep(3)

    # Run it again, this time it should produce output and then start a new command
    obs = session.execute(ExecuteBashAction(command="sleep 15", security_risk="LOW"))

    assert "3" in obs.output  # Should see the final output from the previous command
    assert obs.metadata.exit_code == -1  # -1 indicates new command is still running
    assert session.prev_status == BashCommandStatus.NO_CHANGE_TIMEOUT

    session.close()


def test_interactive_command():
    session = BashSession(work_dir=os.getcwd(), no_change_timeout_seconds=3)
    session.initialize()

    # Test interactive command with blocking=True
    obs = session.execute(
        ExecuteBashAction(
            command="read -p 'Enter name: ' name && echo \"Hello $name\"",
            security_risk="LOW",
        )
    )

    assert "Enter name:" in obs.output
    assert obs.metadata.exit_code == -1  # -1 indicates command is still running
    assert session.prev_status == BashCommandStatus.NO_CHANGE_TIMEOUT
    assert obs.metadata.suffix == get_no_change_timeout_suffix(3)
    assert obs.metadata.prefix == ""

    # Send input
    obs = session.execute(
        ExecuteBashAction(command="John", is_input=True, security_risk="LOW")
    )

    assert "Hello John" in obs.output
    assert obs.metadata.exit_code == 0
    assert obs.metadata.suffix == "\n[The command completed with exit code 0.]"
    assert obs.metadata.prefix == ""
    assert session.prev_status == BashCommandStatus.COMPLETED

    # Test multiline command input
    obs = session.execute(ExecuteBashAction(command="cat << EOF", security_risk="LOW"))

    assert obs.metadata.exit_code == -1
    assert session.prev_status == BashCommandStatus.NO_CHANGE_TIMEOUT
    assert obs.metadata.suffix == get_no_change_timeout_suffix(3)
    assert obs.metadata.prefix == ""

    obs = session.execute(
        ExecuteBashAction(command="line 1", is_input=True, security_risk="LOW")
    )

    assert obs.metadata.exit_code == -1
    assert session.prev_status == BashCommandStatus.NO_CHANGE_TIMEOUT
    assert obs.metadata.suffix == get_no_change_timeout_suffix(3)
    assert obs.metadata.prefix == "[Below is the output of the previous command.]\n"

    obs = session.execute(
        ExecuteBashAction(command="line 2", is_input=True, security_risk="LOW")
    )

    assert obs.metadata.exit_code == -1
    assert session.prev_status == BashCommandStatus.NO_CHANGE_TIMEOUT
    assert obs.metadata.suffix == get_no_change_timeout_suffix(3)
    assert obs.metadata.prefix == "[Below is the output of the previous command.]\n"

    obs = session.execute(
        ExecuteBashAction(command="EOF", is_input=True, security_risk="LOW")
    )

    assert "line 1" in obs.output and "line 2" in obs.output
    assert obs.metadata.exit_code == 0
    assert obs.metadata.suffix == "\n[The command completed with exit code 0.]"
    assert obs.metadata.prefix == ""

    session.close()


def test_ctrl_c():
    session = BashSession(work_dir=os.getcwd(), no_change_timeout_seconds=2)
    session.initialize()

    # Start infinite loop
    obs = session.execute(
        ExecuteBashAction(
            command="while true; do echo 'looping'; sleep 3; done", security_risk="LOW"
        ),
    )

    assert "looping" in obs.output
    assert obs.metadata.suffix == get_no_change_timeout_suffix(2)
    assert obs.metadata.prefix == ""
    assert obs.metadata.exit_code == -1  # -1 indicates command is still running
    assert session.prev_status == BashCommandStatus.NO_CHANGE_TIMEOUT

    # Send Ctrl+C
    obs = session.execute(
        ExecuteBashAction(command="C-c", is_input=True, security_risk="LOW")
    )

    # Check that the process was interrupted (exit code can be 1 or 130
    # depending on the shell/OS)
    assert obs.metadata.exit_code in (
        1,
        130,
    )  # Accept both common exit codes for interrupted processes
    assert "CTRL+C was sent" in obs.metadata.suffix
    assert obs.metadata.prefix == ""
    assert session.prev_status == BashCommandStatus.COMPLETED

    session.close()


def test_empty_command_errors():
    session = BashSession(work_dir=os.getcwd())
    session.initialize()

    # Test empty command without previous command
    obs = session.execute(ExecuteBashAction(command="", security_risk="LOW"))

    assert obs.error is True
    assert obs.output == "ERROR: No previous running command to retrieve logs from."
    assert "There was an error during command execution." in obs.agent_observation
    assert (
        "ERROR: No previous running command to retrieve logs from."
        in obs.agent_observation
    )
    assert obs.metadata.exit_code == -1
    assert obs.metadata.prefix == ""
    assert obs.metadata.suffix == ""
    assert session.prev_status is None

    session.close()


def test_command_output_continuation():
    """Test that we can continue to get output from a long-running command.

    This test has been modified to be more robust against timing issues.
    """
    session = BashSession(work_dir=os.getcwd(), no_change_timeout_seconds=1)
    session.initialize()

    # Start a command that produces output slowly but with longer sleep time
    # to ensure we hit the timeout
    obs = session.execute(
        ExecuteBashAction(
            command="for i in {1..5}; do echo $i; sleep 2; done", security_risk="LOW"
        )
    )

    # Check if the command completed immediately or timed out
    if session.prev_status == BashCommandStatus.COMPLETED:
        # If the command completed immediately, verify we got all the output
        logger.info("Command completed immediately", extra={"msg_type": "TEST_INFO"})
        assert "1" in obs.output
        assert "2" in obs.output
        assert "3" in obs.output
        assert "4" in obs.output
        assert "5" in obs.output
        assert "[The command completed with exit code 0.]" in obs.metadata.suffix
    else:
        # If the command timed out, verify we got the timeout message
        assert session.prev_status == BashCommandStatus.NO_CHANGE_TIMEOUT
        assert "1" in obs.output
        assert "[The command has no new output after 1 seconds." in obs.metadata.suffix

        # Continue getting output until we see all numbers
        numbers_seen = set()
        for i in range(1, 6):
            if str(i) in obs.output:
                numbers_seen.add(i)

        # We need to see numbers 2-5 and then the command completion
        while (
            len(numbers_seen) < 5 or session.prev_status != BashCommandStatus.COMPLETED
        ):
            obs = session.execute(
                ExecuteBashAction(command="", is_input=True, security_risk="LOW")
            )

            # Check for numbers in the output
            for i in range(1, 6):
                if str(i) in obs.output and i not in numbers_seen:
                    numbers_seen.add(i)
                    logger.info(
                        f"Found number {i} in output", extra={"msg_type": "TEST_INFO"}
                    )

            # Check if the command has completed
            if session.prev_status == BashCommandStatus.COMPLETED:
                assert (
                    "[The command completed with exit code 0.]" in obs.metadata.suffix
                )
                break
            else:
                assert (
                    "[The command has no new output after 1 seconds."
                    in obs.metadata.suffix
                )
                assert session.prev_status == BashCommandStatus.NO_CHANGE_TIMEOUT

        # Verify we've seen all numbers
        assert numbers_seen == {1, 2, 3, 4, 5}, (
            f"Expected to see numbers 1-5, but saw {numbers_seen}"
        )

        # Verify the command completed
        assert session.prev_status == BashCommandStatus.COMPLETED

    session.close()


def test_long_output():
    session = BashSession(work_dir=os.getcwd())
    session.initialize()

    # Generate a long output that may exceed buffer size
    obs = session.execute(
        ExecuteBashAction(
            command='for i in {1..5000}; do echo "Line $i"; done', security_risk="LOW"
        )
    )

    assert "Line 1" in obs.output
    assert "Line 5000" in obs.output
    assert obs.metadata.exit_code == 0
    assert obs.metadata.prefix == ""
    assert obs.metadata.suffix == "\n[The command completed with exit code 0.]"

    session.close()


def test_long_output_exceed_history_limit():
    session = BashSession(work_dir=os.getcwd())
    session.initialize()

    # Generate a long output that may exceed buffer size
    obs = session.execute(
        ExecuteBashAction(
            command='for i in {1..50000}; do echo "Line $i"; done', security_risk="LOW"
        )
    )

    assert "Previous command outputs are truncated" in obs.metadata.prefix
    assert "Line 40000" in obs.output
    assert "Line 50000" in obs.output
    assert obs.metadata.exit_code == 0
    assert obs.metadata.suffix == "\n[The command completed with exit code 0.]"

    session.close()


def test_multiline_command():
    session = BashSession(work_dir=os.getcwd())
    session.initialize()

    # Test multiline command with PS2 prompt disabled
    obs = session.execute(
        ExecuteBashAction(
            command="""if true; then
echo "inside if"
fi""",
            security_risk="LOW",
        )
    )

    assert "inside if" in obs.output
    assert obs.metadata.exit_code == 0
    assert obs.metadata.prefix == ""
    assert obs.metadata.suffix == "\n[The command completed with exit code 0.]"

    session.close()


def test_python_interactive_input():
    session = BashSession(work_dir=os.getcwd(), no_change_timeout_seconds=2)
    session.initialize()

    # Test Python program that asks for input - properly escaped for bash
    python_script = (
        "name = input('Enter your name: '); age = input('Enter your age: '); "
        "print(f'Hello {name}, you are {age} years old')"
    )

    # Start Python with the interactive script
    obs = session.execute(
        ExecuteBashAction(command=f'python3 -c "{python_script}"', security_risk="LOW")
    )

    assert "Enter your name:" in obs.output
    assert obs.metadata.exit_code == -1  # -1 indicates command is still running
    assert session.prev_status == BashCommandStatus.NO_CHANGE_TIMEOUT

    # Send first input (name)
    obs = session.execute(
        ExecuteBashAction(command="Alice", is_input=True, security_risk="LOW")
    )

    assert "Enter your age:" in obs.output
    assert obs.metadata.exit_code == -1
    assert session.prev_status == BashCommandStatus.NO_CHANGE_TIMEOUT

    # Send second input (age)
    obs = session.execute(
        ExecuteBashAction(command="25", is_input=True, security_risk="LOW")
    )

    assert "Hello Alice, you are 25 years old" in obs.output
    assert obs.metadata.exit_code == 0
    assert obs.metadata.suffix == "\n[The command completed with exit code 0.]"
    assert session.prev_status == BashCommandStatus.COMPLETED

    session.close()
