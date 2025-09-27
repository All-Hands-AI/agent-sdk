"""Abstract base class for sandboxed agent servers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class BashExecutionResult:
    """Result of a bash command execution."""

    def __init__(
        self,
        command_id: str,
        command: str,
        exit_code: int | None = None,
        output: str = "",
    ):
        self.command_id = command_id
        self.command = command
        self.exit_code = exit_code
        self.output = output
        self.is_running = exit_code is None


class SandboxedAgentServer(ABC):
    """Abstract base class for running OpenHands Agent Server in sandboxed environments.

    This class defines the interface that all sandboxed agent server implementations
    must follow. Implementations can be Docker-based, remote API-based, or other
    sandboxing technologies.

    The class is designed to be used as a context manager:

    Example:
        with SomeConcreteServer(host_port=8010) as server:
            # Use server.base_url to connect to the agent server
            conversation = Conversation(agent=agent, host=server.base_url)
            ...
    """

    def __init__(
        self,
        *,
        host_port: int | None = None,
        host: str = "127.0.0.1",
        **kwargs: Any,
    ) -> None:
        """Initialize the sandboxed agent server.

        Args:
            host_port: Port to bind the server to. If None, finds available port.
            host: Host interface to bind to. Defaults to localhost.
            **kwargs: Additional implementation-specific arguments.
        """
        self.host_port = host_port
        self.host = host
        self._base_url: str | None = None

    @property
    def base_url(self) -> str:
        """Get the base URL where the agent server is accessible.

        Returns:
            The base URL (e.g., "http://127.0.0.1:8010")

        Raises:
            RuntimeError: If the server is not running or URL is not available.
        """
        if self._base_url is None:
            raise RuntimeError("Server is not running or base URL is not available")
        return self._base_url

    @abstractmethod
    def __enter__(self) -> SandboxedAgentServer:
        """Start the sandboxed agent server.

        This method should:
        1. Start the agent server in the sandboxed environment
        2. Wait for the server to become healthy/ready
        3. Set self._base_url to the accessible URL
        4. Return self for context manager usage

        Returns:
            Self for context manager chaining.

        Raises:
            RuntimeError: If the server fails to start or become ready.
        """
        pass

    @abstractmethod
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Stop the sandboxed agent server and clean up resources.

        This method should:
        1. Stop the agent server
        2. Clean up any resources (containers, processes, etc.)
        3. Reset internal state

        Args:
            exc_type: Exception type if an exception occurred.
            exc_val: Exception value if an exception occurred.
            exc_tb: Exception traceback if an exception occurred.
        """
        pass

    @abstractmethod
    def _wait_for_health(self, timeout: float = 120.0) -> None:
        """Wait for the agent server to become healthy and ready.

        This method should poll the server's health endpoint until it responds
        successfully or the timeout is reached.

        Args:
            timeout: Maximum time to wait in seconds.

        Raises:
            RuntimeError: If the server doesn't become healthy within the timeout.
        """
        pass

    @abstractmethod
    def execute_bash(
        self, command: str, cwd: str | None = None, timeout: int = 300
    ) -> BashExecutionResult:
        """Execute a bash command in the sandboxed environment.

        Args:
            command: The bash command to execute
            cwd: The current working directory (optional)
            timeout: Maximum execution time in seconds (default: 300)

        Returns:
            BashExecutionResult containing command ID, exit code, and output

        Raises:
            RuntimeError: If the server is not running or command execution fails
        """
        pass

    @abstractmethod
    def upload_file(self, local_path: str | Path, remote_path: str) -> bool:
        """Upload a file to the sandboxed environment.

        Args:
            local_path: Path to the local file to upload
            remote_path: Target path in the sandboxed environment

        Returns:
            True if upload was successful, False otherwise

        Raises:
            RuntimeError: If the server is not running or upload fails
        """
        pass

    @abstractmethod
    def upload_file_content(self, content: str | bytes, remote_path: str) -> bool:
        """Upload file content to the sandboxed environment.

        Args:
            content: File content as string or bytes
            remote_path: Target path in the sandboxed environment

        Returns:
            True if upload was successful, False otherwise

        Raises:
            RuntimeError: If the server is not running or upload fails
        """
        pass

    @abstractmethod
    def download_file(
        self, remote_path: str, local_path: str | Path | None = None
    ) -> bytes | None:
        """Download a file from the sandboxed environment.

        Args:
            remote_path: Path to the file in the sandboxed environment
            local_path: Local path to save the file (optional, returns bytes if None)

        Returns:
            File content as bytes if local_path is None, otherwise None

        Raises:
            RuntimeError: If the server is not running or download fails
        """
        pass
