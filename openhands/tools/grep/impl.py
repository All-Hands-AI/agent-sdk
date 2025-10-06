"""Grep tool executor implementation."""

import fnmatch
import os
import re
import subprocess
from pathlib import Path

from openhands.sdk.tool import ToolExecutor
from openhands.tools.grep.definition import GrepAction, GrepObservation
from openhands.tools.utils import (
    _check_ripgrep_available,
    _log_ripgrep_fallback_warning,
)


class GrepExecutor(ToolExecutor[GrepAction, GrepObservation]):
    """Executor for grep content search operations.

    This implementation prefers ripgrep for performance but falls back to
    regular grep if ripgrep is not available:
    - Primary: Uses ripgrep with case-insensitive search and file listing
    - Fallback: Uses regular grep command with similar functionality
    """

    def __init__(self, working_dir: str):
        """Initialize the grep executor.

        Args:
            working_dir: The working directory to use as the base for searches
        """
        self.working_dir = Path(working_dir).resolve()
        self._ripgrep_available = _check_ripgrep_available()
        if not self._ripgrep_available:
            _log_ripgrep_fallback_warning("grep", "regular grep command")

    def __call__(self, action: GrepAction) -> GrepObservation:
        """Execute grep content search using ripgrep or fallback to regular grep.

        Args:
            action: The grep action containing pattern, path, and include filter

        Returns:
            GrepObservation with matching file paths
        """
        try:
            # Determine search path
            if action.path:
                search_path = Path(action.path).resolve()
                if not search_path.is_dir():
                    return GrepObservation(
                        matches=[],
                        pattern=action.pattern,
                        search_path=str(search_path),
                        include_pattern=action.include,
                        error=f"Search path '{action.path}' is not a valid directory",
                    )
            else:
                search_path = self.working_dir

            # Validate regex pattern
            try:
                re.compile(action.pattern)
            except re.error as e:
                return GrepObservation(
                    matches=[],
                    pattern=action.pattern,
                    search_path=str(search_path),
                    include_pattern=action.include,
                    error=f"Invalid regex pattern: {e}",
                )

            if self._ripgrep_available:
                return self._execute_with_ripgrep(action, search_path)
            else:
                return self._execute_with_grep(action, search_path)

        except Exception as e:
            # Determine search path for error reporting
            try:
                if action.path:
                    error_search_path = str(Path(action.path).resolve())
                else:
                    error_search_path = str(self.working_dir)
            except Exception:
                error_search_path = "unknown"

            return GrepObservation(
                matches=[],
                pattern=action.pattern,
                search_path=error_search_path,
                include_pattern=action.include,
                error=str(e),
            )

    def _execute_with_ripgrep(
        self, action: GrepAction, search_path: Path
    ) -> GrepObservation:
        """Execute grep content search using ripgrep."""
        # Build ripgrep command: rg -li pattern --sortr=modified
        cmd = [
            "rg",
            "-l",  # files-with-matches
            "-i",  # ignore-case
            action.pattern,
            str(search_path),
            "--sortr=modified",
        ]

        # Apply include glob pattern if specified
        if action.include:
            cmd.extend(["-g", action.include])

        # Execute ripgrep
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30, check=False
        )

        # Parse output into file paths
        matches = []
        if result.stdout:
            for line in result.stdout.strip().split("\n"):
                if line:
                    matches.append(line)
                    # Limit to first 100 files
                    if len(matches) >= 100:
                        break

        truncated = len(matches) >= 100

        return GrepObservation(
            matches=matches,
            pattern=action.pattern,
            search_path=str(search_path),
            include_pattern=action.include,
            truncated=truncated,
        )

    def _execute_with_grep(
        self, action: GrepAction, search_path: Path
    ) -> GrepObservation:
        """Execute grep content search using regular grep command."""
        # Find files to search
        files_to_search = []

        # Walk through directory to find files
        for root, dirs, files in os.walk(search_path):
            for file in files:
                file_path = os.path.join(root, file)

                # Apply include pattern filter if specified
                if action.include:
                    if not fnmatch.fnmatch(file, action.include):
                        continue

                # Skip binary files and common non-text files
                if self._is_likely_text_file(file_path):
                    files_to_search.append(file_path)

        # Sort files by modification time (newest first)
        files_to_search.sort(key=lambda f: os.path.getmtime(f), reverse=True)

        # Limit files to search to avoid performance issues
        files_to_search = files_to_search[:1000]

        # Build grep command: grep -l -i pattern files...
        cmd = ["grep", "-l", "-i", action.pattern] + files_to_search

        # Execute grep
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30, check=False
        )

        # Parse output into file paths
        matches = []
        if result.stdout:
            for line in result.stdout.strip().split("\n"):
                if line:
                    matches.append(line)
                    # Limit to first 100 files
                    if len(matches) >= 100:
                        break

        truncated = len(matches) >= 100

        return GrepObservation(
            matches=matches,
            pattern=action.pattern,
            search_path=str(search_path),
            include_pattern=action.include,
            truncated=truncated,
        )

    def _is_likely_text_file(self, file_path: str) -> bool:
        """Check if a file is likely to be a text file."""
        # Skip common binary file extensions
        binary_extensions = {
            ".exe",
            ".dll",
            ".so",
            ".dylib",
            ".bin",
            ".obj",
            ".o",
            ".a",
            ".lib",
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".bmp",
            ".ico",
            ".svg",
            ".webp",
            ".mp3",
            ".mp4",
            ".avi",
            ".mov",
            ".wav",
            ".flac",
            ".ogg",
            ".zip",
            ".tar",
            ".gz",
            ".bz2",
            ".xz",
            ".7z",
            ".rar",
            ".pdf",
            ".doc",
            ".docx",
            ".xls",
            ".xlsx",
            ".ppt",
            ".pptx",
            ".pyc",
            ".pyo",
            ".class",
            ".jar",
        }

        file_ext = os.path.splitext(file_path)[1].lower()
        if file_ext in binary_extensions:
            return False

        # Try to read a small portion to check if it's text
        try:
            with open(file_path, "rb") as f:
                chunk = f.read(1024)
                if b"\0" in chunk:  # Null bytes indicate binary file
                    return False
                # Try to decode as UTF-8
                chunk.decode("utf-8")
                return True
        except (OSError, UnicodeDecodeError):
            return False
