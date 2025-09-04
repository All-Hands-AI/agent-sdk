"""Abstract base class for terminal sessions."""

import os
from abc import ABC, abstractmethod
from enum import Enum

from openhands.tools.execute_bash.definition import (
    ExecuteBashAction,
    ExecuteBashObservation,
)


class TerminalCommandStatus(Enum):
    """Status of a terminal command execution."""

    CONTINUE = "continue"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"
    NO_CHANGE_TIMEOUT = "no_change_timeout"
    HARD_TIMEOUT = "hard_timeout"


class TerminalSession(ABC):
    """Abstract base class for terminal sessions.

    This class defines the common interface for all terminal session implementations,
    including tmux-based, subprocess-based, and PowerShell-based sessions.
    """

    def __init__(
        self,
        work_dir: str,
        username: str | None = None,
        max_memory_mb: int | None = None,
        no_change_timeout_seconds: int | None = None,
    ):
        """Initialize the terminal session.

        Args:
            work_dir: Working directory for the session
            username: Optional username for the session
            max_memory_mb: Optional memory limit in MB
            no_change_timeout_seconds: Timeout for no output change
        """
        self.work_dir = work_dir
        self.username = username
        self.max_memory_mb = max_memory_mb
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
