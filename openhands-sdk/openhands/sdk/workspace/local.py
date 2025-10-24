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
    """Local workspace operations with an optional server-owned root fence.

    Notes:
    - The workspace root fence is a class-level setting owned by the server.
      It can be set programmatically via `LocalWorkspace.set_workspace_root(...)`.
    - There is no equivalent in RemoteWorkspace; remote calls rely on the
      server's configured fence and cannot widen it.
    - By default, if not set explicitly, the root resolves to
      `Path("workspace").resolve()`.
    """

    # Server-owned fence for local path operations. Only applies to LocalWorkspace.
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
        cwd_str = str(cwd) if cwd is not None else str(self.working_dir)
        result = execute_command(
            command,
            cwd=cwd_str,
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
        """Upload (copy) a file locally using shutil.copy2."""
        source = Path(source_path)
        destination = Path(destination_path)

        logger.debug(f"Local file upload: {source} -> {destination}")

        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
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
        """Download (copy) a file locally using shutil.copy2."""
        source = Path(source_path)
        destination = Path(destination_path)

        logger.debug(f"Local file download: {source} -> {destination}")

        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
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
        """Get the git changes for the repository at the path given."""
        target = (Path(self.working_dir) / path).resolve()
        return get_git_changes(target)

    def git_diff(self, path: str | Path) -> GitDiff:
        """Get the git diff for the file at the path given."""
        target = (Path(self.working_dir) / path).resolve()
        return get_git_diff(target)
