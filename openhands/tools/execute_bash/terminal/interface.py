"""Abstract interface for terminal backends."""

import os
from abc import ABC, abstractmethod

from openhands.tools.execute_bash.definition import (
    ExecuteBashAction,
    ExecuteBashObservation,
)


class TerminalInterface(ABC):
    """Abstract interface for terminal backends.

    This interface abstracts the low-level terminal operations, allowing
    different backends (tmux, subprocess, PowerShell) to be used with
    the same high-level session controller logic.
    """

    def __init__(
        self,
        work_dir: str,
        username: str | None = None,
    ):
        """Initialize the terminal interface.

        Args:
            work_dir: Working directory for the terminal
            username: Optional username for the terminal session
        """
        self.work_dir = work_dir
        self.username = username
        self._initialized = False
        self._closed = False

    @abstractmethod
    def initialize(self) -> None:
        """Initialize the terminal backend.

        This should set up the terminal session, configure the shell,
        and prepare it for command execution.
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """Clean up the terminal backend.

        This should properly terminate the terminal session and
        clean up any resources.
        """
        pass

    @abstractmethod
    def send_keys(self, text: str, enter: bool = True) -> None:
        """Send text/keys to the terminal.

        Args:
            text: Text or key sequence to send
            enter: Whether to send Enter key after the text
        """
        pass

    @abstractmethod
    def read_screen(self) -> str:
        """Read the current terminal screen content.

        Returns:
            Current visible content of the terminal screen
        """
        pass

    @abstractmethod
    def clear_screen(self) -> None:
        """Clear the terminal screen and history."""
        pass

    @abstractmethod
    def interrupt(self) -> bool:
        """Send interrupt signal (Ctrl+C) to the terminal.

        Returns:
            True if interrupt was sent successfully, False otherwise
        """
        pass

    @abstractmethod
    def is_running(self) -> bool:
        """Check if a command is currently running in the terminal.

        Returns:
            True if a command is running, False otherwise
        """
        pass

    @property
    def initialized(self) -> bool:
        """Check if the terminal is initialized."""
        return self._initialized

    @property
    def closed(self) -> bool:
        """Check if the terminal is closed."""
        return self._closed

    def is_powershell(self) -> bool:
        """Check if this is a PowerShell terminal.

        Returns:
            True if this is a PowerShell terminal, False otherwise
        """
        return False


class TerminalSessionBase(ABC):
    """Abstract base class for terminal sessions.

    This class defines the common interface for all terminal session implementations,
    including tmux-based, subprocess-based, and PowerShell-based sessions.
    """

    def __init__(
        self,
        work_dir: str,
        username: str | None = None,
        no_change_timeout_seconds: int | None = None,
    ):
        """Initialize the terminal session.

        Args:
            work_dir: Working directory for the session
            username: Optional username for the session
            no_change_timeout_seconds: Timeout for no output change
        """
        self.work_dir = work_dir
        self.username = username
        self.no_change_timeout_seconds = no_change_timeout_seconds
        self._initialized = False
        self._closed = False
        self._cwd = os.path.abspath(work_dir)

    @abstractmethod
    def initialize(self) -> None:
        """Initialize the terminal session."""
        pass

    @abstractmethod
    def execute(self, action: ExecuteBashAction) -> ExecuteBashObservation:
        """Execute a command in the terminal session.

        Args:
            action: The bash action to execute

        Returns:
            ExecuteBashObservation with the command result
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """Clean up the terminal session."""
        pass

    @abstractmethod
    def interrupt(self) -> bool:
        """Interrupt the currently running command (equivalent to Ctrl+C).

        Returns:
            True if interrupt was successful, False otherwise
        """
        pass

    @abstractmethod
    def is_running(self) -> bool:
        """Check if a command is currently running.

        Returns:
            True if a command is running, False otherwise
        """
        pass

    @property
    def cwd(self) -> str:
        """Get the current working directory."""
        return self._cwd

    def __del__(self) -> None:
        """Ensure the session is closed when the object is destroyed."""
        self.close()
