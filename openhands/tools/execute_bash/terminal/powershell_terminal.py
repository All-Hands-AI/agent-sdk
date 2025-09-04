"""PowerShell-based terminal backend implementation."""

import os
import platform
import signal
import subprocess
import threading
import time
from collections import deque
from typing import Deque

from openhands.sdk.logger import get_logger
from openhands.tools.execute_bash.terminal.interface import TerminalInterface


logger = get_logger(__name__)


class PowershellTerminal(TerminalInterface):
    """PowerShell-based terminal backend.

    This backend uses PowerShell to provide a terminal session
    that can work on both Windows and Unix systems (with PowerShell Core).
    """

    def __init__(
        self,
        work_dir: str,
        username: str | None = None,
    ):
        super().__init__(work_dir, username)
        # Use a PowerShell-compatible prompt
        self.PS1 = "PS OpenHands> "
        self.process: subprocess.Popen | None = None
        self.output_buffer: Deque[str] = deque(maxlen=10000)  # Circular buffer
        self.output_lock = threading.Lock()
        self.reader_thread: threading.Thread | None = None
        self._current_command_running = False

    def initialize(self) -> None:
        """Initialize the PowerShell terminal session."""
        if self._initialized:
            return

        # Determine PowerShell command based on platform
        if platform.system() == "Windows":
            # On Windows, try PowerShell Core first, then Windows PowerShell
            powershell_commands = ["pwsh", "powershell"]
        else:
            # On Unix systems, use PowerShell Core
            powershell_commands = ["pwsh"]

        powershell_cmd = None
        for cmd in powershell_commands:
            try:
                # Test if the command exists
                subprocess.run([cmd, "-Version"], capture_output=True, timeout=5)
                powershell_cmd = [cmd, "-NoLogo", "-NoExit", "-Command", "-"]
                break
            except (
                subprocess.TimeoutExpired,
                subprocess.CalledProcessError,
                FileNotFoundError,
            ):
                continue

        if not powershell_cmd:
            raise RuntimeError(
                "PowerShell not found. Please install PowerShell Core (pwsh)."
            )

        logger.debug(f"Initializing PowerShell terminal with command: {powershell_cmd}")

        # Set up environment
        env = os.environ.copy()

        # Start the subprocess
        kwargs = {
            "stdin": subprocess.PIPE,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "cwd": self.work_dir,
            "env": env,
            "text": True,
            "bufsize": 0,  # Unbuffered
        }

        # On Unix systems, create new process group for signal handling
        if platform.system() != "Windows":
            kwargs["preexec_fn"] = os.setsid

        self.process = subprocess.Popen(powershell_cmd, **kwargs)

        # Start output reader thread
        self.reader_thread = threading.Thread(
            target=self._read_output_continuously, daemon=True
        )
        self.reader_thread.start()

        # Configure PowerShell
        time.sleep(0.2)  # Let PowerShell start up

        # Set up custom prompt and basic configuration
        setup_commands = [
            # Set custom prompt
            f'function prompt {{ return "{self.PS1}" }}',
            # Set location to work directory
            f'Set-Location "{self.work_dir}"',
            # Configure output formatting
            "$OutputEncoding = [System.Text.Encoding]::UTF8",
            # Disable progress bars that can interfere with output
            '$ProgressPreference = "SilentlyContinue"',
        ]

        for cmd in setup_commands:
            self._send_command_internal(cmd)
            time.sleep(0.1)

        logger.debug(f"PowerShell terminal initialized with work dir: {self.work_dir}")
        self._initialized = True
        self.clear_screen()

    def _read_output_continuously(self) -> None:
        """Continuously read output from the PowerShell process in a separate thread."""
        if not self.process or not self.process.stdout:
            return

        try:
            while self.process.poll() is None:
                try:
                    # Read character by character to avoid blocking
                    char = self.process.stdout.read(1)
                    if char:
                        with self.output_lock:
                            # Add to buffer, maintaining a rolling window
                            if len(self.output_buffer) == 0:
                                self.output_buffer.append(char)
                            else:
                                # Append to last string if recent, otherwise start new
                                self.output_buffer[-1] += char
                                # Split into lines if we get too long
                                if len(self.output_buffer[-1]) > 1000:
                                    lines = self.output_buffer[-1].split("\n")
                                    self.output_buffer[-1] = lines[0]
                                    for line in lines[1:]:
                                        self.output_buffer.append(line)
                except Exception as e:
                    logger.debug(f"Error reading PowerShell output: {e}")
                    break
        except Exception as e:
            logger.error(f"Output reader thread error: {e}")

    def close(self) -> None:
        """Clean up the PowerShell terminal."""
        if self._closed:
            return

        if self.process:
            try:
                # Send exit command
                if self.process.stdin and not self.process.stdin.closed:
                    self.process.stdin.write("exit\n")
                    self.process.stdin.flush()

                # Wait briefly for graceful exit
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    # Force kill if needed
                    if self.process.poll() is None:
                        if platform.system() == "Windows":
                            self.process.terminate()
                        else:
                            os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                        try:
                            self.process.wait(timeout=1)
                        except subprocess.TimeoutExpired:
                            if platform.system() == "Windows":
                                self.process.kill()
                            else:
                                os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
            except Exception as e:
                logger.error(f"Error closing PowerShell terminal: {e}")
            finally:
                self.process = None

        if self.reader_thread and self.reader_thread.is_alive():
            self.reader_thread.join(timeout=1)

        self._closed = True

    def _send_command_internal(self, command: str) -> None:
        """Internal method to send command without logging."""
        if not self.process or not self.process.stdin:
            raise RuntimeError("PowerShell terminal is not initialized")

        try:
            self.process.stdin.write(command + "\n")
            self.process.stdin.flush()
        except Exception as e:
            logger.error(f"Failed to send command to PowerShell: {e}")
            raise

    def send_keys(self, text: str, enter: bool = True) -> None:
        """Send text/keys to the PowerShell process.

        Args:
            text: Text or key sequence to send
            enter: Whether to send Enter key after the text
        """
        if not self._initialized:
            raise RuntimeError("PowerShell terminal is not initialized")

        # Handle special key sequences
        if text.startswith("C-") and len(text) == 3:
            # Handle Ctrl+key sequences
            key = text[2].lower()
            if key == "c":
                self.interrupt()
                return
            elif key == "l":
                # Clear screen
                text = "Clear-Host"
            # For other Ctrl sequences, just send the text as-is for now

        if enter:
            self._send_command_internal(text)
            self._current_command_running = True
        else:
            # Send without newline (for interactive input)
            if self.process and self.process.stdin:
                self.process.stdin.write(text)
                self.process.stdin.flush()

    def read_screen(self) -> str:
        """Read the current terminal screen content.

        Returns:
            Current visible content of the terminal screen
        """
        if not self._initialized:
            raise RuntimeError("PowerShell terminal is not initialized")

        with self.output_lock:
            # Join all buffer content
            content = "".join(self.output_buffer)

            # Simulate terminal screen by taking last ~50 lines
            lines = content.split("\n")
            if len(lines) > 50:
                lines = lines[-50:]

            return "\n".join(lines)

    def clear_screen(self) -> None:
        """Clear the terminal screen and history."""
        if not self._initialized:
            return

        # Clear the output buffer
        with self.output_lock:
            self.output_buffer.clear()

        # Send clear command
        self._send_command_internal("Clear-Host")
        time.sleep(0.1)

    def interrupt(self) -> bool:
        """Send interrupt signal (Ctrl+C) to the PowerShell process.

        Returns:
            True if interrupt was sent successfully, False otherwise
        """
        if not self._initialized or not self.process:
            return False

        try:
            if platform.system() == "Windows":
                # On Windows, send Ctrl+C via stdin
                if self.process.stdin:
                    self.process.stdin.write("\x03")  # Ctrl+C character
                    self.process.stdin.flush()
            else:
                # On Unix systems, send SIGINT to the process group
                os.killpg(os.getpgid(self.process.pid), signal.SIGINT)

            self._current_command_running = False
            return True
        except Exception as e:
            logger.error(f"Failed to interrupt PowerShell process: {e}")
            return False

    def is_running(self) -> bool:
        """Check if a command is currently running.

        Returns:
            True if a command is running, False otherwise
        """
        if not self._initialized or not self.process:
            return False

        # Check if process is still alive
        if self.process.poll() is not None:
            return False

        # Check if we're waiting for a command to complete
        # by looking at the current screen content
        try:
            content = self.read_screen()
            # If screen ends with our PowerShell prompt, no command is running
            return not content.rstrip().endswith(self.PS1.rstrip())
        except Exception:
            return self._current_command_running

    def is_powershell(self) -> bool:
        """Check if this is a PowerShell terminal.

        Returns:
            True since this is a PowerShell terminal
        """
        return True
