"""PowerShell-based terminal session implementation."""

import os
import platform
import select
import signal
import subprocess
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


logger = get_logger(__name__)


class PowershellSession(TerminalSession):
    """PowerShell-based terminal session with soft timeout and stateful terminal logic.

    This implementation maintains a persistent PowerShell process to ensure statefulness
    (environment variables, working directory, etc.) while providing soft timeout
    and interrupt capabilities.
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
        self._powershell_process: subprocess.Popen | None = None
        self._current_command_process: subprocess.Popen | None = None
        self._process_lock = Lock()
        self.prev_status: TerminalCommandStatus | None = None

    def initialize(self) -> None:
        """Initialize the PowerShell session."""
        if platform.system() != "Windows":
            # Try to use PowerShell Core (pwsh) on non-Windows systems
            powershell_cmd = "pwsh"
        else:
            # Use Windows PowerShell
            powershell_cmd = "powershell"

        # Test if PowerShell is available
        try:
            result = subprocess.run(
                [powershell_cmd, "-Command", "Write-Host 'PowerShell Available'"],
                capture_output=True,
                text=True,
                timeout=5.0,
            )
            if result.returncode != 0:
                raise RuntimeError(f"PowerShell not available: {result.stderr}")
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            raise RuntimeError(f"PowerShell not available: {e}")

        self._powershell_cmd = powershell_cmd
        logger.debug(f"PowerShell session initialized with work dir: {self.work_dir}")
        self._initialized = True

    def close(self) -> None:
        """Clean up the PowerShell session."""
        if self._closed:
            return

        with self._process_lock:
            if self._current_command_process:
                self._safe_terminate_process(self._current_command_process)
                self._current_command_process = None

            if self._powershell_process:
                self._safe_terminate_process(self._powershell_process)
                self._powershell_process = None

        self._closed = True

    def interrupt(self) -> bool:
        """Interrupt the currently running command (equivalent to Ctrl+C)."""
        if not self._initialized:
            return False

        with self._process_lock:
            if self._current_command_process:
                try:
                    if platform.system() == "Windows":
                        # On Windows, use taskkill to terminate the process tree
                        subprocess.run(
                            [
                                "taskkill",
                                "/F",
                                "/T",
                                "/PID",
                                str(self._current_command_process.pid),
                            ],
                            capture_output=True,
                        )
                    else:
                        # On Unix-like systems, send SIGINT to the process group
                        pgid = os.getpgid(self._current_command_process.pid)
                        os.killpg(pgid, signal.SIGINT)
                    return True
                except (ProcessLookupError, OSError) as e:
                    logger.warning(f"Failed to interrupt PowerShell command: {e}")
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
        self, process: subprocess.Popen, use_sigkill: bool = False
    ) -> None:
        """Safely terminate a PowerShell process."""
        if not process or process.poll() is not None:
            return

        try:
            if platform.system() == "Windows":
                # On Windows, use taskkill for forceful termination
                if use_sigkill:
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                        capture_output=True,
                    )
                else:
                    # Try graceful termination first
                    process.terminate()
                    try:
                        process.wait(timeout=2.0)
                    except subprocess.TimeoutExpired:
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                            capture_output=True,
                        )
            else:
                # On Unix-like systems
                signal_to_send = signal.SIGKILL if use_sigkill else signal.SIGTERM
                try:
                    pgid = os.getpgid(process.pid)
                    os.killpg(pgid, signal_to_send)
                    process.wait(timeout=2.0)
                except (ProcessLookupError, subprocess.TimeoutExpired):
                    if not use_sigkill:
                        # Try force kill
                        try:
                            pgid = os.getpgid(process.pid)
                            os.killpg(pgid, signal.SIGKILL)
                            process.wait(timeout=1.0)
                        except (ProcessLookupError, subprocess.TimeoutExpired):
                            pass

        except Exception as e:
            logger.warning(f"Error terminating PowerShell process: {e}")

    def _update_working_directory(self, command: str) -> None:
        """Update the current working directory if the command changed it."""
        # Check if command contains Set-Location or cd
        if any(cmd in command.lower() for cmd in ["set-location", "cd ", "chdir"]):
            try:
                # Get the current working directory
                result = subprocess.run(
                    [
                        self._powershell_cmd,
                        "-Command",
                        "Get-Location | Select-Object -ExpandProperty Path",
                    ],
                    cwd=self._cwd,
                    capture_output=True,
                    text=True,
                    timeout=5.0,
                )
                if result.returncode == 0:
                    new_cwd = result.stdout.strip()
                    if new_cwd and os.path.isdir(new_cwd):
                        self._cwd = new_cwd
            except (subprocess.TimeoutExpired, OSError) as e:
                logger.warning(f"Failed to update working directory: {e}")

    def execute(self, action: ExecuteBashAction) -> ExecuteBashObservation:
        """Execute a command in the PowerShell session."""
        if not self._initialized:
            raise RuntimeError("PowerShell session is not initialized")

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
            # For PowerShell subprocess implementation, we can't easily send input
            # This is a limitation compared to tmux
            return ExecuteBashObservation(
                output="ERROR: Interactive input not supported in PowerShell subprocess mode.",  # noqa: E501
                error=True,
            )

        # Execute the command
        return self._execute_command(command, action.timeout)

    def _execute_command(
        self, command: str, timeout: float | None
    ) -> ExecuteBashObservation:
        """Execute a single PowerShell command with timeout and output streaming."""
        output_lines = []
        timed_out = False
        interrupted = False
        start_time = time.time()
        last_output_time = start_time

        # Prepare the PowerShell command with working directory
        full_command = f"Set-Location '{self._cwd}'; {command}"

        try:
            with self._process_lock:
                # Start the PowerShell command process
                self._current_command_process = subprocess.Popen(
                    [self._powershell_cmd, "-Command", full_command],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                    cwd=self._cwd,
                )

            process = self._current_command_process
            logger.debug(f"Started PowerShell command process PID: {process.pid}")

            # Read output with timeout handling
            if process.stdout:
                while process.poll() is None:
                    current_time = time.time()

                    # Check for hard timeout
                    if timeout and (current_time - start_time) > timeout:
                        logger.debug(
                            f"PowerShell command timed out after {timeout} seconds"
                        )
                        self._safe_terminate_process(process)
                        timed_out = True
                        break

                    # Check for soft timeout (no output change)
                    if (
                        not timeout  # Only apply soft timeout if no hard timeout
                        and (current_time - last_output_time)
                        > self.no_change_timeout_seconds
                    ):
                        logger.debug(
                            f"PowerShell command soft timeout after {self.no_change_timeout_seconds} seconds"  # noqa: E501
                        )
                        # Don't terminate, just mark as timed out
                        timed_out = True
                        break

                    # Check for available output (Unix-like systems only)
                    if platform.system() != "Windows":
                        try:
                            ready, _, _ = select.select(
                                [process.stdout], [], [], POLL_INTERVAL
                            )
                            if ready:
                                line = process.stdout.readline()
                                if line:
                                    output_lines.append(line)
                                    last_output_time = current_time
                            else:
                                time.sleep(POLL_INTERVAL)
                        except (OSError, ValueError):
                            # select() not available or stream closed
                            line = process.stdout.readline()
                            if line:
                                output_lines.append(line)
                                last_output_time = current_time
                            else:
                                time.sleep(POLL_INTERVAL)
                    else:
                        # On Windows, we can't use select() with pipes
                        # Use a simple polling approach
                        try:
                            line = process.stdout.readline()
                            if line:
                                output_lines.append(line)
                                last_output_time = current_time
                            else:
                                time.sleep(POLL_INTERVAL)
                        except Exception:
                            time.sleep(POLL_INTERVAL)

                # Read any remaining output
                if process.stdout and not process.stdout.closed:
                    try:
                        remaining = process.stdout.read()
                        if remaining:
                            output_lines.append(remaining)
                    except Exception as e:
                        logger.warning(
                            f"Error reading remaining PowerShell output: {e}"
                        )

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

            # Handle negative exit codes (signals on Unix-like systems)
            if exit_code and exit_code < 0:
                interrupted = True

        except Exception as e:
            logger.error(f"Error executing PowerShell command '{command}': {e}")
            with self._process_lock:
                if self._current_command_process:
                    self._safe_terminate_process(self._current_command_process)
            return ExecuteBashObservation(
                output=f"Error during PowerShell command execution: {e}",
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

        # Update working directory after command execution
        if exit_code == 0:  # Only update on successful commands
            self._update_working_directory(command)

        # Create metadata
        metadata = CmdOutputMetadata()
        metadata.working_dir = self._cwd
        metadata.exit_code = exit_code if exit_code is not None else -1

        # Set appropriate suffix based on command status
        if timed_out:
            if timeout:
                metadata.suffix = (
                    f"\n[The PowerShell command timed out after {timeout} seconds. "
                    f"{TIMEOUT_MESSAGE_TEMPLATE}]"
                )
            else:
                metadata.suffix = (
                    f"\n[The PowerShell command has no new output after "
                    f"{self.no_change_timeout_seconds} seconds. {TIMEOUT_MESSAGE_TEMPLATE}]"  # noqa: E501
                )
        elif interrupted:
            metadata.suffix = "\n[The PowerShell command was interrupted.]"
        else:
            metadata.suffix = (
                f"\n[The PowerShell command completed with exit code {exit_code}.]"
            )

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
