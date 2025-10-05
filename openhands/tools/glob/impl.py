"""Glob tool executor implementation."""

import subprocess
from pathlib import Path

from openhands.sdk.tool import ToolExecutor
from openhands.tools.glob.definition import GlobAction, GlobObservation


class GlobExecutor(ToolExecutor[GlobAction, GlobObservation]):
    """Executor for glob pattern matching operations.

    This implementation
    - Uses rg --files to list all files
    - Filters by glob pattern with -g flag
    - Sorted by modification time (--sortr=modified)
    """

    def __init__(self, working_dir: str):
        """Initialize the glob executor.

        Args:
            working_dir: The working directory to use as the base for searches
        """
        self.working_dir = Path(working_dir).resolve()

    def __call__(self, action: GlobAction) -> GlobObservation:
        """Execute glob pattern matching using ripgrep.

        Args:
            action: The glob action containing pattern and optional path

        Returns:
            GlobObservation with matching files or error information
        """
        try:
            # Determine search path
            if action.path:
                search_path = Path(action.path).resolve()
                if not search_path.is_dir():
                    return GlobObservation(
                        files=[],
                        pattern=action.pattern,
                        search_path=str(search_path),
                        error=f"Search path '{action.path}' is not a valid directory",
                    )
            else:
                search_path = self.working_dir

            # Build ripgrep command: rg --files {path} -g {pattern} --sortr=modified
            cmd = [
                "rg",
                "--files",
                str(search_path),
                "-g",
                action.pattern,
                "--sortr=modified",
            ]

            # Execute ripgrep
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30, check=False
            )

            # Parse output into file paths
            file_paths = []
            if result.stdout:
                for line in result.stdout.strip().split("\n"):
                    if line:
                        file_paths.append(line)
                        # Limit to first 100 files
                        if len(file_paths) >= 100:
                            break

            truncated = len(file_paths) >= 100

            return GlobObservation(
                files=file_paths,
                pattern=action.pattern,
                search_path=str(search_path),
                truncated=truncated,
            )

        except Exception as e:
            # Determine search path for error reporting
            try:
                if action.path:
                    error_search_path = str(Path(action.path).resolve())
                else:
                    error_search_path = str(self.working_dir)
            except Exception:
                error_search_path = "unknown"

            return GlobObservation(
                files=[],
                pattern=action.pattern,
                search_path=error_search_path,
                error=str(e),
            )
