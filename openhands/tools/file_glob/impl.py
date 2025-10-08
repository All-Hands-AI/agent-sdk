"""Glob tool executor implementation."""

import os
import subprocess
from glob import glob
from pathlib import Path

from openhands.sdk.tool import ToolExecutor
from openhands.tools.file_glob.definition import GlobAction, GlobObservation
from openhands.tools.utils import (
    _check_ripgrep_available,
    _log_ripgrep_fallback_warning,
)


class GlobExecutor(ToolExecutor[GlobAction, GlobObservation]):
    """Executor for glob pattern matching operations.

    This implementation prefers ripgrep for performance but falls back to
    Python's glob module if ripgrep is not available:
    - Primary: Uses rg --files to list all files, filters by glob pattern with -g flag
    - Fallback: Uses Python's glob.glob() for pattern matching
    """

    def __init__(self, working_dir: str):
        """Initialize the glob executor.

        Args:
            working_dir: The working directory to use as the base for searches
        """
        self.working_dir = Path(working_dir).resolve()
        self._ripgrep_available = _check_ripgrep_available()
        if not self._ripgrep_available:
            _log_ripgrep_fallback_warning("glob", "Python glob module")

    def __call__(self, action: GlobAction) -> GlobObservation:
        """Execute glob pattern matching using ripgrep or fallback to Python glob.

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

            if self._ripgrep_available:
                return self._execute_with_ripgrep(action, search_path)
            else:
                return self._execute_with_glob(action, search_path)

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

    def _execute_with_ripgrep(
        self, action: GlobAction, search_path: Path
    ) -> GlobObservation:
        """Execute glob pattern matching using ripgrep."""
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

    def _execute_with_glob(
        self, action: GlobAction, search_path: Path
    ) -> GlobObservation:
        """Execute glob pattern matching using Python's glob module."""
        # Change to search directory for glob to work correctly
        original_cwd = os.getcwd()
        try:
            os.chdir(search_path)

            # Ripgrep's -g flag is always recursive, so we need to make the pattern
            # recursive if it doesn't already contain **
            pattern = action.pattern
            if "**" not in pattern:
                # Convert non-recursive patterns like "*.py" to "**/*.py"
                # to match ripgrep's recursive behavior
                pattern = f"**/{pattern}"

            # Use glob to find matching files
            matches = glob(pattern, recursive=True)

            # Convert to absolute paths (without resolving symlinks) a
            # nd sort by modification time
            file_paths = []
            for match in matches:
                # Use absolute() instead of resolve() to avoid resolving symlinks
                abs_path = str((search_path / match).absolute())
                if os.path.isfile(abs_path):
                    file_paths.append((abs_path, os.path.getmtime(abs_path)))

            # Sort by modification time (newest first) and extract paths
            file_paths.sort(key=lambda x: x[1], reverse=True)
            sorted_files = [path for path, _ in file_paths[:100]]

            truncated = len(file_paths) > 100

            return GlobObservation(
                files=sorted_files,
                pattern=action.pattern,
                search_path=str(search_path),
                truncated=truncated,
            )
        finally:
            os.chdir(original_cwd)
