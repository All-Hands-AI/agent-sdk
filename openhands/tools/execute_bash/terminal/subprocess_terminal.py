"""PTY-based terminal backend implementation (replaces pipe-based subprocess)."""

import fcntl
import os
import pty
import re
import select
import signal
import subprocess
import threading
import time
import uuid
from collections import deque
from typing import Deque

from openhands.sdk.logger import get_logger
from openhands.tools.execute_bash.constants import CMD_OUTPUT_PS1_END, HISTORY_LIMIT
from openhands.tools.execute_bash.metadata import CmdOutputMetadata
from openhands.tools.execute_bash.terminal import TerminalInterface


logger = get_logger(__name__)


class SubprocessTerminal(TerminalInterface):
    """PTY-backed terminal backend.

    Creates an interactive bash in a pseudoterminal (PTY) so programs behave as if
    attached to a real terminal. Initialization uses a sentinel-based handshake
    and prompt detection instead of blind sleeps.
    """

    def __init__(
        self,
        work_dir: str,
        username: str | None = None,
    ):
        super().__init__(work_dir, username)
        self.PS1 = CmdOutputMetadata.to_ps1_prompt()
        self.process: subprocess.Popen | None = None
        self._pty_master_fd: int | None = None
        self.output_buffer: Deque[str] = deque(maxlen=HISTORY_LIMIT)  # Circular buffer
        self.output_lock = threading.Lock()
        self.reader_thread: threading.Thread | None = None
        self._current_command_running = False

    # ------------------------- Lifecycle -------------------------

    def initialize(self) -> None:
        """Initialize the PTY terminal session."""
        if self._initialized:
            return

        env = os.environ.copy()
        env["PS1"] = self.PS1
        env["PS2"] = ""
        env["TERM"] = "xterm-256color"

        bash_cmd = ["/bin/bash", "-i"]

        # Create a PTY; give the slave to the child, keep the master
        master_fd, slave_fd = pty.openpty()

        logger.debug("Initializing PTY terminal with: %s", " ".join(bash_cmd))
        try:
            self.process = subprocess.Popen(
                bash_cmd,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                cwd=self.work_dir,
                env=env,
                text=False,  # bytes I/O
                bufsize=0,
                preexec_fn=os.setsid,  # new process group for signal handling
                close_fds=True,
            )
        finally:
            # Parent must close its copy of the slave FD
            try:
                os.close(slave_fd)
            except Exception:
                pass

        self._pty_master_fd = master_fd

        # Set master FD non-blocking
        flags = fcntl.fcntl(self._pty_master_fd, fcntl.F_GETFL)
        fcntl.fcntl(self._pty_master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        # Start output reader thread
        self.reader_thread = threading.Thread(
            target=self._read_output_continuously_pty, daemon=True
        )
        self.reader_thread.start()
        self._initialized = True

        # ===== Deterministic readiness (no blind sleeps) =====
        # 1) Nudge bash to render something
        self._write_pty(b"\n")

        # 2) Single atomic init line: clear PROMPT_COMMAND, set PS2/PS1, print sentinel
        sentinel = f"__OH_READY_{uuid.uuid4().hex}__"
        init_cmd = (
            f"export PROMPT_COMMAND='export PS1=\"{self.PS1}\"'; "
            f'export PS2=""; '
            f'printf "{sentinel}\\n"'
        ).encode("utf-8", "ignore")

        self._write_pty(init_cmd + b"\n")
        if not self._wait_for_output(sentinel, timeout=8.0):
            # Retry once in case initial write raced with shell bring-up
            logger.debug("Sentinel not seen, retrying init command once")
            self._write_pty(init_cmd + b"\n")
            if not self._wait_for_output(sentinel, timeout=8.0):
                raise RuntimeError("Shell did not become ready (sentinel not seen)")

        # 3) Wait for prompt to actually be visible
        if not self._wait_for_prompt(timeout=5.0):
            # Final nudge
            self._write_pty(b"\n")
            if not self._wait_for_prompt(timeout=2.0):
                raise RuntimeError("Prompt not visible after init")

        logger.debug("PTY terminal initialized with work dir: %s", self.work_dir)
        self.clear_screen()

    def close(self) -> None:
        """Clean up the PTY terminal."""
        if self._closed:
            return

        try:
            if self.process:
                # Try a graceful exit
                try:
                    self._write_pty(b"exit\n")
                except Exception:
                    pass
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    # Escalate
                    try:
                        os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                        self.process.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
        except Exception as e:
            logger.error(f"Error closing PTY terminal: {e}")
        finally:
            # Reader thread stop: close master FD; thread exits on read error/EOF
            try:
                if self._pty_master_fd is not None:
                    os.close(self._pty_master_fd)
            except Exception:
                pass
            self._pty_master_fd = None

            if self.reader_thread and self.reader_thread.is_alive():
                self.reader_thread.join(timeout=1)

            self.process = None
            self._closed = True

    # ------------------------- I/O Core -------------------------

    def _write_pty(self, data: bytes) -> None:
        if not self._initialized and self._pty_master_fd is None:
            # allow init path to call before _initialized flips
            raise RuntimeError("PTY master FD not ready")
        if self._pty_master_fd is None:
            raise RuntimeError("PTY terminal is not initialized")
        try:
            os.write(self._pty_master_fd, data)
        except Exception as e:
            logger.error(f"Failed to write to PTY: {e}")
            raise

    def _read_output_continuously_pty(self) -> None:
        """Continuously read output from the PTY master in a separate thread."""
        fd = self._pty_master_fd
        if fd is None:
            return

        try:
            while True:
                # Exit early if process died
                if self.process and self.process.poll() is not None:
                    break

                # Use select to avoid busy spin
                r, _, _ = select.select([fd], [], [], 0.1)
                if not r:
                    continue

                try:
                    chunk = os.read(fd, 4096)
                    if not chunk:
                        break  # EOF
                    # Normalize newlines; PTY typically uses \n already
                    text = chunk.decode("utf-8", errors="replace")
                    with self.output_lock:
                        if self.output_buffer and len(self.output_buffer[-1]) < 1000:
                            self.output_buffer[-1] += text
                        else:
                            self.output_buffer.append(text)
                except OSError:
                    # Would-block or FD closed
                    continue
                except Exception as e:
                    logger.debug(f"Error reading PTY output: {e}")
                    break
        except Exception as e:
            logger.error(f"PTY reader thread error: {e}")

    # ------------------------- Readiness Helpers -------------------------

    def _wait_for_output(self, pattern: str | re.Pattern, timeout: float = 5.0) -> bool:
        """Wait until the output buffer contains pattern (regex or literal)."""
        deadline = time.time() + timeout
        is_regex = hasattr(pattern, "search")
        while time.time() < deadline:
            # quick yield to reader thread
            if self._pty_master_fd is not None:
                select.select([], [], [], 0.02)
            with self.output_lock:
                data = "".join(self.output_buffer)
            if is_regex:
                assert isinstance(pattern, re.Pattern)
                if pattern.search(data):
                    return True
            else:
                assert isinstance(pattern, str)
                if pattern in data:
                    return True
        return False

    def _wait_for_prompt(self, timeout: float = 5.0) -> bool:
        """Wait until the screen ends with our PS1 end marker (prompt visible)."""
        pat = re.compile(re.escape(CMD_OUTPUT_PS1_END.rstrip()) + r"\s*$")
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self.output_lock:
                tail = "".join(self.output_buffer)[-4096:]
            if pat.search(tail):
                return True
            time.sleep(0.05)
        return False

    # ------------------------- Public API -------------------------

    def send_keys(self, text: str, enter: bool = True) -> None:
        """Send keystrokes to the PTY.

        Supports:
          - Plain text
          - Ctrl sequences: 'C-a'..'C-z' (Ctrl+C sends ^C byte)
          - Special names: 'ENTER','TAB','BS','ESC','UP','DOWN','LEFT','RIGHT',
                           'HOME','END','PGUP','PGDN','C-L','C-D'
        """
        if not self._initialized:
            raise RuntimeError("PTY terminal is not initialized")

        specials = {
            "ENTER": b"\n",
            "TAB": b"\t",
            "BS": b"\x7f",  # Backspace (DEL)
            "ESC": b"\x1b",
            "UP": b"\x1b[A",
            "DOWN": b"\x1b[B",
            "RIGHT": b"\x1b[C",
            "LEFT": b"\x1b[D",
            "HOME": b"\x1b[H",
            "END": b"\x1b[F",
            "PGUP": b"\x1b[5~",
            "PGDN": b"\x1b[6~",
            "C-L": b"\x0c",  # Ctrl+L
            "C-D": b"\x04",  # Ctrl+D (EOF)
        }

        upper = text.upper().strip()
        payload: bytes | None = None

        # Named specials
        if upper in specials:
            payload = specials[upper]
        # Generic Ctrl-<letter>, including C-C (preferred over sending SIGINT directly)
        elif upper.startswith(("C-", "CTRL-", "CTRL+")):
            # last char after dash/plus is the key
            key = upper.split("-", 1)[-1].split("+", 1)[-1]
            if len(key) == 1 and "A" <= key <= "Z":
                payload = bytes([ord(key) & 0x1F])
            else:
                # Unknown form; fall back to raw text
                payload = text.encode("utf-8", "ignore")
        else:
            # Plain text
            payload = text.encode("utf-8", "ignore")

        # Append newline if requested (and not already newline)
        if enter and (payload is not None) and not payload.endswith(b"\n"):
            payload += b"\n"

        self._write_pty(payload)
        # Heuristic: consider a command "running" if we sent a newline
        self._current_command_running = self._current_command_running or enter

    def read_screen(self) -> str:
        """Read the current terminal screen content."""
        if not self._initialized:
            raise RuntimeError("PTY terminal is not initialized")

        with self.output_lock:
            content = "".join(self.output_buffer)
            lines = content.split("\n")
            return "\n".join(lines)

    def clear_screen(self) -> None:
        """Clear the terminal screen and history and ensure a prompt is visible."""
        if not self._initialized:
            return

        # 1) Drop our local buffer
        with self.output_lock:
            self.output_buffer.clear()

        # 2) Ask bash to repaint the prompt like tmux does
        try:
            # Ctrl+L to clear and redraw
            self._write_pty(b"\x0c")
        except Exception:
            pass

        # 3) Wait a moment for bash to render the prompt
        #    (reuse the existing helper that checks for CMD_OUTPUT_PS1_END)
        self._wait_for_prompt(timeout=2.0)

    def interrupt(self) -> bool:
        """Send SIGINT to the PTY process group (fallback to signal-based interrupt)."""
        if not self._initialized or not self.process:
            return False

        try:
            os.killpg(os.getpgid(self.process.pid), signal.SIGINT)
            self._current_command_running = False
            return True
        except Exception as e:
            logger.error(f"Failed to interrupt subprocess: {e}")
            return False

    def is_running(self) -> bool:
        """Heuristic: command running if not at PS1 prompt and process alive."""
        if not self._initialized or not self.process:
            return False

        # Check if process is still alive
        if self.process.poll() is not None:
            return False

        try:
            content = self.read_screen()
            # If screen ends with prompt, no command is running
            return not content.rstrip().endswith(CMD_OUTPUT_PS1_END.rstrip())
        except Exception:
            return self._current_command_running
