"""Grep tool executor implementation."""

import fnmatch
import os
import re
from pathlib import Path

from openhands.sdk.tool import ToolExecutor
from openhands.tools.grep.definition import GrepAction, GrepObservation


class GrepExecutor(ToolExecutor[GrepAction, GrepObservation]):
    """Executor for grep content search operations."""

    def __init__(self, working_dir: str):
        """Initialize the grep executor.

        Args:
            working_dir: The working directory to use as the base for searches
        """
        self.working_dir = Path(working_dir).resolve()

    def __call__(self, action: GrepAction) -> GrepObservation:
        """Execute grep content search.

        Args:
            action: The grep action containing pattern, path, and include filter

        Returns:
            GrepObservation with matching lines or error information
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

            # Compile regex pattern
            try:
                regex = re.compile(action.pattern)
            except re.error as e:
                return GrepObservation(
                    matches=[],
                    pattern=action.pattern,
                    search_path=str(search_path),
                    include_pattern=action.include,
                    error=f"Invalid regex pattern: {e}",
                )

            # Find all files to search
            files_to_search = []
            for root, dirs, files in os.walk(search_path):
                # Skip hidden directories
                dirs[:] = [d for d in dirs if not d.startswith(".")]

                for file in files:
                    # Skip hidden files
                    if file.startswith("."):
                        continue

                    file_path = Path(root) / file

                    # Apply include filter if specified
                    if action.include:
                        if not fnmatch.fnmatch(file, action.include):
                            continue

                    # Only search text files (skip binary files)
                    if self._is_text_file(file_path):
                        files_to_search.append(file_path)

            # Sort files by modification time (newest first)
            files_to_search.sort(key=lambda x: x.stat().st_mtime, reverse=True)

            # Search for pattern in files
            matches = []
            for file_path in files_to_search:
                try:
                    with open(file_path, encoding="utf-8", errors="ignore") as f:
                        for line_num, line in enumerate(f, 1):
                            line = line.rstrip("\n\r")
                            if regex.search(line):
                                matches.append(
                                    {
                                        "file_path": str(file_path),
                                        "line_number": line_num,
                                        "line_content": line,
                                    }
                                )

                                # Limit to first 100 matches
                                if len(matches) >= 100:
                                    break

                    # Break if we've reached the limit
                    if len(matches) >= 100:
                        break

                except (OSError, UnicodeDecodeError):
                    # Skip files that can't be read
                    continue

            truncated = len(matches) >= 100

            return GrepObservation(
                matches=matches,
                pattern=action.pattern,
                search_path=str(search_path),
                include_pattern=action.include,
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

            return GrepObservation(
                matches=[],
                pattern=action.pattern,
                search_path=error_search_path,
                include_pattern=action.include,
                error=str(e),
            )

    def _is_text_file(self, file_path: Path) -> bool:
        """Check if a file is likely a text file.

        Args:
            file_path: Path to the file to check

        Returns:
            True if the file is likely a text file, False otherwise
        """
        # Check file extension
        text_extensions = {
            ".txt",
            ".py",
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".html",
            ".htm",
            ".css",
            ".scss",
            ".sass",
            ".less",
            ".json",
            ".xml",
            ".yaml",
            ".yml",
            ".toml",
            ".ini",
            ".cfg",
            ".conf",
            ".md",
            ".rst",
            ".tex",
            ".sh",
            ".bash",
            ".zsh",
            ".fish",
            ".ps1",
            ".bat",
            ".cmd",
            ".c",
            ".cpp",
            ".cc",
            ".cxx",
            ".h",
            ".hpp",
            ".hxx",
            ".java",
            ".kt",
            ".scala",
            ".go",
            ".rs",
            ".rb",
            ".php",
            ".pl",
            ".pm",
            ".r",
            ".R",
            ".sql",
            ".dockerfile",
            ".makefile",
            ".cmake",
            ".gitignore",
            ".gitattributes",
            ".editorconfig",
            ".env",
            ".properties",
            ".log",
        }

        if file_path.suffix.lower() in text_extensions:
            return True

        # Check common filenames without extensions
        text_filenames = {
            "readme",
            "license",
            "changelog",
            "makefile",
            "dockerfile",
            "jenkinsfile",
            "vagrantfile",
            "gemfile",
            "rakefile",
            "procfile",
        }

        if file_path.name.lower() in text_filenames:
            return True

        # For files without clear extensions, try to read a small sample
        try:
            with open(file_path, "rb") as f:
                sample = f.read(1024)
                # Check if the sample contains mostly printable ASCII characters
                if not sample:
                    return True  # Empty file is considered text
                # Count printable characters
                printable_chars = sum(
                    1 for byte in sample if 32 <= byte <= 126 or byte in (9, 10, 13)
                )
                return printable_chars / len(sample) > 0.7
        except (OSError, PermissionError):
            return False
