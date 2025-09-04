"""Subprocess-based terminal session implementation."""

import os
import select
import signal
import subprocess
import tempfile
import time
from threading import Lock

from openhands.sdk.logger import get_logger
from openhands.tools.execute_bash.constants import (
    NO_CHANGE_TIMEOUT_SECONDS,
    POLL_INTERVAL,
    TIMEOUT_MESSAGE_TEMPLATE,
)
from openhands.tools.execute_bash.definition import (
    ExecuteBashAction,
    ExecuteBashObservation,
)
from openhands.tools.execute_bash.metadata import CmdOutputMetadata
from openhands.tools.execute_bash.sessions.base import (
    TerminalCommandStatus,
    TerminalSession,
)
from openhands.tools.execute_bash.utils.command import split_bash_commands


logger = get_logger(__name__)


class SubprocessBashSession(TerminalSession):
    """Subprocess-based bash session with soft timeout and stateful terminal logic.

    This implementation maintains a persistent bash process to ensure statefulness
    (environment variables, working directory, etc.) while providing soft timeout
    and interrupt capabilities similar to the tmux implementation.
    """

    def __init__(
        self,
        work_dir: str,
        username: str | None = None,
        max_memory_mb: int | None = None,
        no_change_timeout_seconds: int | None = None,
    ):
        super().__init__(work_dir, username, max_memory_mb, no_change_timeout_seconds)
        self.no_change_timeout_seconds = (
            no_change_timeout_seconds or NO_CHANGE_TIMEOUT_SECONDS
        )
        self._bash_process: subprocess.Popen | None = None
        self._current_command_process: subprocess.Popen | None = None
        self._process_lock = Lock()
        self._env_file: str | None = None
        self._env_vars: dict[str, str] = {}
        self._closed = False
        self.prev_status: TerminalCommandStatus | None = None

    def initialize(self) -> None:
        """Initialize the subprocess bash session."""
        # Create a temporary file to store environment variables
        fd, self._env_file = tempfile.mkstemp(suffix=".env", prefix="bash_session_")
        os.close(fd)

        # Initialize environment with current environment
        self._env_vars = dict(os.environ)
        self._env_vars["PWD"] = self.work_dir

        logger.debug(
            f"Subprocess bash session initialized with work dir: {self.work_dir}"
        )
        self._initialized = True

    def close(self) -> None:
        """Clean up the subprocess session."""
        if self._closed:
            return

        with self._process_lock:
            if self._current_command_process:
                self._safe_terminate_process(self._current_command_process)
                self._current_command_process = None

            if self._bash_process:
                self._safe_terminate_process(self._bash_process)
                self._bash_process = None

        # Clean up environment file
        if self._env_file and os.path.exists(self._env_file):
            try:
                os.unlink(self._env_file)
            except OSError:
                pass

        self._closed = True

    def interrupt(self) -> bool:
        """Interrupt the currently running command (equivalent to Ctrl+C)."""
        if not self._initialized:
            return False

        with self._process_lock:
            if self._current_command_process:
                try:
                    # Send SIGINT to the process group
                    pgid = os.getpgid(self._current_command_process.pid)
                    os.killpg(pgid, signal.SIGINT)
                    return True
                except (ProcessLookupError, OSError) as e:
                    logger.warning(f"Failed to interrupt command: {e}")
                    return False
        return False

    def is_running(self) -> bool:
        """Check if a command is currently running."""
        with self._process_lock:
            return (
                self._current_command_process is not None
                and self._current_command_process.poll() is None
            )

    def _safe_terminate_process(
        self, process: subprocess.Popen, signal_to_send: int = signal.SIGTERM
    ) -> None:
        """Safely terminate a process and its process group."""
        if not process or process.poll() is not None:
            return

        try:
            # Try to terminate the entire process group
            pgid = os.getpgid(process.pid)
            os.killpg(pgid, signal_to_send)

            # Wait a bit for graceful termination
            try:
                process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                # Force kill if graceful termination failed
                if signal_to_send != signal.SIGKILL:
                    os.killpg(pgid, signal.SIGKILL)
                    process.wait(timeout=1.0)

        except (ProcessLookupError, OSError):
            # Process might have already terminated
            try:
                process.kill()
                process.wait(timeout=1.0)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                pass

    def _save_environment(self) -> None:
        """Save current environment variables to the environment file."""
        if not self._env_file:
            return

        try:
            with open(self._env_file, "w") as f:
                for key, value in self._env_vars.items():
                    # Escape special characters in environment values
                    escaped_value = value.replace("\\", "\\\\").replace('"', '\\"')
                    f.write(f'export {key}="{escaped_value}"\n')
        except OSError as e:
            logger.warning(f"Failed to save environment: {e}")

    def _load_environment(self) -> None:
        """Load environment variables from a command's execution."""
        if not self._env_file:
            return

        try:
            # Run a command to export current environment to our file
            env_cmd = f'env > "{self._env_file}"'
            result = subprocess.run(
                ["bash", "-c", env_cmd],
                cwd=self._cwd,
                env=self._env_vars,
                capture_output=True,
                text=True,
                timeout=5.0,
            )

            if result.returncode == 0:
                # Parse the environment file
                with open(self._env_file, "r") as f:
                    for line in f:
                        line = line.strip()
                        if "=" in line:
                            key, value = line.split("=", 1)
                            self._env_vars[key] = value

        except (subprocess.TimeoutExpired, OSError) as e:
            logger.warning(f"Failed to load environment: {e}")

    def _update_working_directory(self, command: str) -> None:
        """Update the current working directory if the command changed it."""
        # Check if command contains cd
        if "cd " in command:
            try:
                # Get the current working directory by executing the same command
                # sequence and then running pwd
                full_command = f"cd '{self._cwd}' && {command} && pwd"
                result = subprocess.run(
                    ["bash", "-c", full_command],
                    env=self._env_vars,
                    capture_output=True,
                    text=True,
                    timeout=2.0,
                )
                if result.returncode == 0:
                    new_cwd = result.stdout.strip()
                    if new_cwd and os.path.isdir(new_cwd):
                        self._cwd = new_cwd
                        self._env_vars["PWD"] = new_cwd
            except (subprocess.TimeoutExpired, OSError) as e:
                logger.warning(f"Failed to update working directory: {e}")

    def execute(self, action: ExecuteBashAction) -> ExecuteBashObservation:
        """Execute a command in the subprocess bash session."""
        if not self._initialized:
            raise RuntimeError("Subprocess bash session is not initialized")
        if self._closed:
            raise RuntimeError("Subprocess bash session has been closed")

        command = action.command.strip()
        is_input = action.is_input

        # Handle empty command for retrieving logs
        if command == "" and not is_input:
            if not self.is_running():
                return ExecuteBashObservation(
                    output="ERROR: No previous running command to retrieve logs from.",
                    error=True,
                )
            # Return current status of running command
            return ExecuteBashObservation(
                output="[Command is still running. Use interrupt() to stop it.]",
                command="",
                metadata=CmdOutputMetadata(),
            )

        # Handle input to running process
        if is_input:
            if not self.is_running():
                return ExecuteBashObservation(
                    output="ERROR: No previous running command to interact with.",
                    error=True,
                )
            # For subprocess implementation, we can't easily send input to running process  # noqa: E501
            # This is a limitation compared to tmux
            return ExecuteBashObservation(
                output="ERROR: Interactive input not supported in subprocess mode.",
                error=True,
            )

        # Check for multiple commands
        split_commands = split_bash_commands(command)
        if len(split_commands) > 1:
            return ExecuteBashObservation(
                output=(
                    f"ERROR: Cannot execute multiple commands at once.\n"
                    f"Please run each command separately OR chain them into a single "
                    f"command via && or ;\nProvided commands:\n"
                    f"{'\n'.join(f'({i + 1}) {cmd}' for i, cmd in enumerate(split_commands))}"  # noqa: E501
                ),
                error=True,
            )

        # Execute the command
        return self._execute_command(command, action.timeout)

    def _execute_command(
        self, command: str, timeout: float | None
    ) -> ExecuteBashObservation:
        """Execute a single command with timeout and output streaming."""
        output_lines = []
        timed_out = False
        interrupted = False
        start_time = time.time()
        last_output_time = start_time

        # Prepare the command with environment setup
        full_command = f"cd '{self._cwd}' && {command}"

        try:
            with self._process_lock:
                # Start the command process
                self._current_command_process = subprocess.Popen(
                    ["bash", "-c", full_command],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                    start_new_session=True,
                    env=self._env_vars,
                    cwd=self._cwd,
                )

            process = self._current_command_process
            logger.debug(f"Started command process PID: {process.pid}")

            # Read output with timeout handling
            if process.stdout:
                while process.poll() is None:
                    current_time = time.time()

                    # Check for hard timeout
                    if timeout and (current_time - start_time) > timeout:
                        logger.debug(f"Command timed out after {timeout} seconds")
                        self._safe_terminate_process(process, signal.SIGTERM)
                        timed_out = True
                        break

                    # Check for soft timeout (no output change)
                    if (
                        not timeout  # Only apply soft timeout if no hard timeout
                        and (current_time - last_output_time)
                        > self.no_change_timeout_seconds
                    ):
                        logger.debug(
                            f"Command soft timeout after {self.no_change_timeout_seconds} seconds"  # noqa: E501
                        )
                        # Don't terminate, just mark as timed out
                        timed_out = True
                        break

                    # Check for available output
                    ready, _, _ = select.select([process.stdout], [], [], POLL_INTERVAL)

                    if ready:
                        line = process.stdout.readline()
                        if line:
                            output_lines.append(line)
                            last_output_time = current_time

                # Read any remaining output
                if process.stdout and not process.stdout.closed:
                    try:
                        remaining = process.stdout.read()
                        if remaining:
                            output_lines.append(remaining)
                    except Exception as e:
                        logger.warning(f"Error reading remaining output: {e}")

            # Get exit code
            exit_code = process.returncode
            if exit_code is None:
                # Process might still be running
                if timed_out:
                    exit_code = -1  # Indicate timeout
                else:
                    try:
                        exit_code = process.wait(timeout=1.0)
                    except subprocess.TimeoutExpired:
                        exit_code = -1

            # Handle negative exit codes (signals)
            if exit_code and exit_code < 0:
                interrupted = True

        except Exception as e:
            logger.error(f"Error executing command '{command}': {e}")
            with self._process_lock:
                if self._current_command_process:
                    self._safe_terminate_process(self._current_command_process)
            return ExecuteBashObservation(
                output=f"Error during command execution: {e}",
                command=command,
                exit_code=-1,
                error=True,
                metadata=CmdOutputMetadata(),
            )
        finally:
            with self._process_lock:
                self._current_command_process = None

        # Process the output
        complete_output = "".join(output_lines)

        # Update environment and working directory after command execution
        if exit_code == 0:  # Only update on successful commands
            self._update_working_directory(command)
            self._load_environment()

        # Create metadata
        metadata = CmdOutputMetadata()
        metadata.working_dir = self._cwd
        metadata.exit_code = exit_code if exit_code is not None else -1

        # Set appropriate suffix based on command status
        if timed_out:
            if timeout:
                metadata.suffix = (
                    f"\n[The command timed out after {timeout} seconds. "
                    f"{TIMEOUT_MESSAGE_TEMPLATE}]"
                )
            else:
                metadata.suffix = (
                    f"\n[The command has no new output after "
                    f"{self.no_change_timeout_seconds} seconds. {TIMEOUT_MESSAGE_TEMPLATE}]"  # noqa: E501
                )
        elif interrupted:
            metadata.suffix = (
                f"\n[The command was interrupted with signal {abs(exit_code)}.]"
            )
        else:
            metadata.suffix = f"\n[The command completed with exit code {exit_code}.]"

        # Update status
        if timed_out:
            if timeout:
                self.prev_status = TerminalCommandStatus.HARD_TIMEOUT
            else:
                self.prev_status = TerminalCommandStatus.NO_CHANGE_TIMEOUT
        elif interrupted:
            self.prev_status = TerminalCommandStatus.INTERRUPTED
        else:
            self.prev_status = TerminalCommandStatus.COMPLETED

        return ExecuteBashObservation(
            output=complete_output,
            command=command,
            exit_code=metadata.exit_code,
            timeout=timed_out,
            metadata=metadata,
        )
