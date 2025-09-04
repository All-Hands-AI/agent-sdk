"""Abstract interface for terminal backends."""

from abc import ABC, abstractmethod


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
        max_memory_mb: int | None = None,
    ):
        """Initialize the terminal interface.

        Args:
            work_dir: Working directory for the terminal
            username: Optional username for the terminal session
            max_memory_mb: Optional memory limit in MB
        """
        self.work_dir = work_dir
        self.username = username
        self.max_memory_mb = max_memory_mb
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
