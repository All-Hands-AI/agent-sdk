"""Glob tool executor implementation."""

import glob
import os
from pathlib import Path

from openhands.sdk.tool import ToolExecutor
from openhands.tools.glob.definition import GlobAction, GlobObservation


class GlobExecutor(ToolExecutor[GlobAction, GlobObservation]):
    """Executor for glob pattern matching operations."""

    def __init__(self, working_dir: str):
        """Initialize the glob executor.

        Args:
            working_dir: The working directory to use as the base for searches
        """
        self.working_dir = Path(working_dir).resolve()

    def __call__(self, action: GlobAction) -> GlobObservation:
        """Execute glob pattern matching.

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

            # Change to search directory for glob operation
            original_cwd = os.getcwd()
            try:
                os.chdir(search_path)

                # Perform glob search
                matches = glob.glob(action.pattern, recursive=True)

                # Convert to absolute paths and filter out directories
                file_paths = []
                for match in matches:
                    full_path = (search_path / match).resolve()
                    if full_path.is_file():
                        file_paths.append(str(full_path))

                # Sort by modification time (newest first)
                file_paths.sort(key=lambda x: os.path.getmtime(x), reverse=True)

                # Limit to first 100 results
                truncated = len(file_paths) > 100
                if truncated:
                    file_paths = file_paths[:100]

                return GlobObservation(
                    files=file_paths,
                    pattern=action.pattern,
                    search_path=str(search_path),
                    truncated=truncated,
                )

            finally:
                os.chdir(original_cwd)

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
