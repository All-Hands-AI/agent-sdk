"""Subprocess-based terminal backend implementation."""

import os
import signal
import subprocess
import threading
import time
from collections import deque
from typing import Deque

from openhands.sdk.logger import get_logger
from openhands.tools.execute_bash.metadata import CmdOutputMetadata
from openhands.tools.execute_bash.sessions.terminal_interface import TerminalInterface


logger = get_logger(__name__)


class SubprocessTerminal(TerminalInterface):
    """Subprocess-based terminal backend.

    This backend uses subprocess.Popen to create a persistent bash session
    that mimics tmux behavior for environments where tmux is not available.
    """

    def __init__(
        self,
        work_dir: str,
        username: str | None = None,
        max_memory_mb: int | None = None,
    ):
        super().__init__(work_dir, username, max_memory_mb)
        self.PS1 = CmdOutputMetadata.to_ps1_prompt()
        self.process: subprocess.Popen | None = None
        self.output_buffer: Deque[str] = deque(maxlen=10000)  # Circular buffer
        self.output_lock = threading.Lock()
        self.reader_thread: threading.Thread | None = None
        self._current_command_running = False

    def initialize(self) -> None:
        """Initialize the subprocess terminal session."""
        if self._initialized:
            return

        # Create bash command with proper user switching if needed
        bash_cmd = ["/bin/bash", "-i"]  # Interactive bash

        # Set up environment
        env = os.environ.copy()
        env["PS1"] = self.PS1
        env["PS2"] = ""
        env["TERM"] = "xterm-256color"

        logger.debug(f"Initializing subprocess terminal with command: {bash_cmd}")

        # Start the subprocess
        self.process = subprocess.Popen(
            bash_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=self.work_dir,
            env=env,
            text=True,
            bufsize=0,  # Unbuffered
            preexec_fn=os.setsid,  # Create new process group for signal handling
        )

        # Start output reader thread
        self.reader_thread = threading.Thread(
            target=self._read_output_continuously, daemon=True
        )
        self.reader_thread.start()

        # Configure the shell
        time.sleep(0.1)  # Let bash start up
        self._send_command_internal(f'export PS1="{self.PS1}"')
        self._send_command_internal('export PS2=""')
        self._send_command_internal('export PROMPT_COMMAND=""')

        # Wait for initial setup to complete
        time.sleep(0.2)

        logger.debug(f"Subprocess terminal initialized with work dir: {self.work_dir}")
        self._initialized = True
        self.clear_screen()

    def _read_output_continuously(self) -> None:
        """Continuously read output from the subprocess in a separate thread."""
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
                    logger.debug(f"Error reading subprocess output: {e}")
                    break
        except Exception as e:
            logger.error(f"Output reader thread error: {e}")

    def close(self) -> None:
        """Clean up the subprocess terminal."""
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
                        os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                        try:
                            self.process.wait(timeout=1)
                        except subprocess.TimeoutExpired:
                            os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
            except Exception as e:
                logger.error(f"Error closing subprocess terminal: {e}")
            finally:
                self.process = None

        if self.reader_thread and self.reader_thread.is_alive():
            self.reader_thread.join(timeout=1)

        self._closed = True

    def _send_command_internal(self, command: str) -> None:
        """Internal method to send command without logging."""
        if not self.process or not self.process.stdin:
            raise RuntimeError("Subprocess terminal is not initialized")

        try:
            self.process.stdin.write(command + "\n")
            self.process.stdin.flush()
        except Exception as e:
            logger.error(f"Failed to send command to subprocess: {e}")
            raise

    def send_keys(self, text: str, enter: bool = True) -> None:
        """Send text/keys to the subprocess.

        Args:
            text: Text or key sequence to send
            enter: Whether to send Enter key after the text
        """
        if not self._initialized:
            raise RuntimeError("Subprocess terminal is not initialized")

        # Handle special key sequences
        if text.startswith("C-") and len(text) == 3:
            # Handle Ctrl+key sequences
            key = text[2].lower()
            if key == "c":
                self.interrupt()
                return
            elif key == "l":
                # Clear screen
                text = "clear"
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
            raise RuntimeError("Subprocess terminal is not initialized")

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

        # Clear the output buffer - this is sufficient for subprocess terminal
        with self.output_lock:
            self.output_buffer.clear()

        # Don't send clear command as it interferes with output capture
        # The buffer clearing is sufficient for our purposes

    def interrupt(self) -> bool:
        """Send interrupt signal (Ctrl+C) to the subprocess.

        Returns:
            True if interrupt was sent successfully, False otherwise
        """
        if not self._initialized or not self.process:
            return False

        try:
            # Send SIGINT to the process group
            os.killpg(os.getpgid(self.process.pid), signal.SIGINT)
            self._current_command_running = False
            return True
        except Exception as e:
            logger.error(f"Failed to interrupt subprocess: {e}")
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
            from openhands.tools.execute_bash.constants import CMD_OUTPUT_PS1_END

            # If screen ends with prompt, no command is running
            return not content.rstrip().endswith(CMD_OUTPUT_PS1_END.rstrip())
        except Exception:
            return self._current_command_running
