import shutil
from pathlib import Path
from typing import ClassVar

from openhands.sdk.git.git_changes import get_git_changes
from openhands.sdk.git.git_diff import get_git_diff
from openhands.sdk.git.models import GitChange, GitDiff
from openhands.sdk.logger import get_logger
from openhands.sdk.utils.command import execute_command
from openhands.sdk.workspace.base import BaseWorkspace
from openhands.sdk.workspace.models import CommandResult, FileOperationResult


logger = get_logger(__name__)


class LocalWorkspace(BaseWorkspace):
    """Mixin providing local workspace operations.

    Server-owned fence:
    - Only applies to LocalWorkspace; RemoteWorkspace has no client-side fence and
      relies on server enforcement.
    - Set programmatically via LocalWorkspace.set_workspace_root(...).
    - Defaults to Path("workspace").resolve() if not set.
    """

    # Server-owned workspace fence for local operations.
    # Can be set programmatically via LocalWorkspace.set_workspace_root(...).
    # Not present in RemoteWorkspace; remote calls rely on the server-side fence.
    _workspace_root: ClassVar[Path | None] = None

    @classmethod
    def set_workspace_root(cls, root: str | Path) -> None:
        cls._workspace_root = Path(root).resolve()

    @classmethod
    def get_workspace_root(cls) -> Path:
        if cls._workspace_root is None:
            cls._workspace_root = Path("workspace").resolve()
        return cls._workspace_root

    def _resolve_under_root(self, rel: str | Path) -> Path:
        root = self.get_workspace_root()
        base = Path(self.working_dir)
        if not base.is_absolute():
            base = (root / base).resolve()
        target = (base / rel).resolve()
        try:
            target.relative_to(root)
        except ValueError as e:
            raise ValueError("path_outside_workspace_root") from e
        return target

    def execute_command(
        self,
        command: str,
        cwd: str | Path | None = None,
        timeout: float = 30.0,
    ) -> CommandResult:
        """Execute a bash command locally.

        Uses the shared shell execution utility to run commands with proper
        timeout handling, output streaming, and error management.

        Args:
            command: The bash command to execute
            cwd: Working directory (optional)
            timeout: Timeout in seconds

        Returns:
            CommandResult: Result with stdout, stderr, exit_code, command, and
                timeout_occurred
        """
        logger.debug(f"Executing local bash command: {command} in {cwd}")
        result = execute_command(
            command,
            cwd=str(cwd) if cwd is not None else str(self.working_dir),
            timeout=timeout,
            print_output=True,
        )
        return CommandResult(
            command=command,
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            timeout_occurred=result.returncode == -1,
        )

    def file_upload(
        self,
        source_path: str | Path,
        destination_path: str | Path,
    ) -> FileOperationResult:
        """Upload (copy) a file locally.

        For local systems, file upload is implemented as a file copy operation
        using shutil.copy2 to preserve metadata.

        Args:
            source_path: Path to the source file
            destination_path: Path where the file should be copied

        Returns:
            FileOperationResult: Result with success status and file information
        """
        source = Path(source_path)
        destination = Path(destination_path)

        logger.debug(f"Local file upload: {source} -> {destination}")

        try:
            # Ensure destination directory exists
            destination.parent.mkdir(parents=True, exist_ok=True)

            # Copy the file with metadata preservation
            shutil.copy2(source, destination)

            return FileOperationResult(
                success=True,
                source_path=str(source),
                destination_path=str(destination),
                file_size=destination.stat().st_size,
            )

        except Exception as e:
            logger.error(f"Local file upload failed: {e}")
            return FileOperationResult(
                success=False,
                source_path=str(source),
                destination_path=str(destination),
                error=str(e),
            )

    def file_download(
        self,
        source_path: str | Path,
        destination_path: str | Path,
    ) -> FileOperationResult:
        """Download (copy) a file locally.

        For local systems, file download is implemented as a file copy operation
        using shutil.copy2 to preserve metadata.

        Args:
            source_path: Path to the source file
            destination_path: Path where the file should be copied

        Returns:
            FileOperationResult: Result with success status and file information
        """
        source = Path(source_path)
        destination = Path(destination_path)

        logger.debug(f"Local file download: {source} -> {destination}")

        try:
            # Ensure destination directory exists
            destination.parent.mkdir(parents=True, exist_ok=True)

            # Copy the file with metadata preservation
            shutil.copy2(source, destination)

            return FileOperationResult(
                success=True,
                source_path=str(source),
                destination_path=str(destination),
                file_size=destination.stat().st_size,
            )

        except Exception as e:
            logger.error(f"Local file download failed: {e}")
            return FileOperationResult(
                success=False,
                source_path=str(source),
                destination_path=str(destination),
                error=str(e),
            )

    def git_changes(self, path: str | Path) -> list[GitChange]:
        """Get the git changes for the repository at the path given.

        Args:
            path: Path to the git repository

        Returns:
            list[GitChange]: List of changes

        Raises:
            Exception: If path is not a git repository or getting changes failed
        """
        path = Path(self.working_dir) / path
        return get_git_changes(path)

    def git_diff(self, path: str | Path) -> GitDiff:
        """Get the git diff for the file at the path given.

        Args:
            path: Path to the file

        Returns:
            GitDiff: Git diff

        Raises:
            Exception: If path is not a git repository or getting diff failed
        """
        path = Path(self.working_dir) / path
        return get_git_diff(path)
