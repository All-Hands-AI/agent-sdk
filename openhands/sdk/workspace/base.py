from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from pydantic import Field

from openhands.sdk.logger import get_logger
from openhands.sdk.utils.models import DiscriminatedUnionMixin


logger = get_logger(__name__)


class BaseWorkspace(DiscriminatedUnionMixin, ABC):
    """Abstract base mixin for workspace."""

    working_dir: str = Field(
        description="The working directory for agent operations and tool execution."
    )

    @abstractmethod
    def execute_command(
        self,
        command: str,
        cwd: str | Path | None = None,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        """Execute a bash command on the system.

        Args:
            command: The bash command to execute
            cwd: Working directory for the command (optional)
            timeout: Timeout in seconds (defaults to 30.0)

        Returns:
            dict: Result containing stdout, stderr, exit_code, and other metadata

        Raises:
            Exception: If command execution fails
        """
        ...

    @abstractmethod
    def file_upload(
        self,
        source_path: str | Path,
        destination_path: str | Path,
    ) -> dict[str, Any]:
        """Upload a file to the system.

        Args:
            source_path: Path to the source file
            destination_path: Path where the file should be uploaded

        Returns:
            dict: Result containing success status and metadata

        Raises:
            Exception: If file upload fails
        """
        ...

    @abstractmethod
    def file_download(
        self,
        source_path: str | Path,
        destination_path: str | Path,
    ) -> dict[str, Any]:
        """Download a file from the system.

        Args:
            source_path: Path to the source file on the system
            destination_path: Path where the file should be downloaded

        Returns:
            dict: Result containing success status and metadata

        Raises:
            Exception: If file download fails
        """
        ...
