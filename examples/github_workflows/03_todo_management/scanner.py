#!/usr/bin/env python3
"""
TODO Scanner for OpenHands Automated TODO Management

Scans for `# TODO(openhands)` comments in Python, TypeScript, and Java files.
"""

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        # Log to stderr to avoid JSON interference
        logging.StreamHandler(sys.stderr),
    ],
)
logger = logging.getLogger(__name__)


def scan_file_for_todos(file_path: Path) -> list[dict]:
    """Scan a single file for TODO(openhands) comments."""
    # Only scan specific file extensions
    if file_path.suffix.lower() not in {".py", ".ts", ".java"}:
        logger.debug(f"Skipping file {file_path} (unsupported extension)")
        return []

    # Skip test files and example files that contain mock TODOs
    file_str = str(file_path)
    if (
        "/test" in file_str
        or "/tests/" in file_str
        or "test_" in file_path.name
        # Skip examples
        or "/examples/github_workflows/03_todo_management/" in file_str
    ):
        logger.debug(f"Skipping test/example file: {file_path}")
        return []

    logger.debug(f"Scanning file: {file_path}")

    try:
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except (OSError, UnicodeDecodeError) as e:
        logger.warning(f"Failed to read file {file_path}: {e}")
        return []

    todos = []
    todo_pattern = re.compile(r"TODO\(openhands\)(?::\s*(.*))?", re.IGNORECASE)
    in_docstring = False
    docstring_delimiter = None

    for line_num, line in enumerate(lines, 1):
        # Track docstring state - handle single line and multi-line docstrings
        triple_double_count = line.count('"""')
        triple_single_count = line.count("'''")

        if triple_double_count > 0:
            if triple_double_count == 2:  # Single line docstring
                # Don't change in_docstring state for single line docstrings
                pass
            elif not in_docstring:
                in_docstring = True
                docstring_delimiter = '"""'
            elif docstring_delimiter == '"""':
                in_docstring = False
                docstring_delimiter = None
        elif triple_single_count > 0:
            if triple_single_count == 2:  # Single line docstring
                # Don't change in_docstring state for single line docstrings
                pass
            elif not in_docstring:
                in_docstring = True
                docstring_delimiter = "'''"
            elif docstring_delimiter == "'''":
                in_docstring = False
                docstring_delimiter = None
        match = todo_pattern.search(line)
        if match:
            stripped_line = line.strip()

            # Skip TODOs that have already been processed by the workflow
            if (
                "pull/" in line  # Contains PR URL
                or "TODO(in progress:" in line  # In progress marker
                or "TODO(implemented:" in line  # Implemented marker
                or "TODO(completed:" in line  # Completed marker
                or "github.com/" in line  # Contains GitHub URL
                # Contains any URL
                or "https://" in line
            ):
                logger.debug(
                    f"Skipping already processed TODO in {file_path}:"
                    f"{line_num}: {stripped_line}"
                )
                continue

            # Skip false positives
            if (
                in_docstring  # Skip TODOs inside docstrings
                or '"""' in line
                or "'''" in line
                or stripped_line.startswith("Scans for")
                or stripped_line.startswith("This script processes")
                or "description=" in line
                # Skip test file mock data
                or ".write_text(" in line
                # Skip test file mock data
                or 'content = """' in line
                # Skip print statements
                or "print(" in line
                # Skip print statements with double quotes
                or 'print("' in line
                # Skip print statements with single quotes
                or "print('" in line
                or (
                    "TODO(openhands)" in line and '"' in line and line.count('"') >= 2  # noqa: E501
                )  # Skip quoted strings
            ):
                logger.debug(
                    f"Skipping false positive in {file_path}:{line_num}: "
                    f"{stripped_line}"
                )
                continue

            # Extract initial description from the TODO line
            description = match.group(1).strip() if match.group(1) else ""
            full_text = line.strip()

            # Look ahead for continuation lines that are also comments
            continuation_lines = []
            for next_line_idx in range(line_num, len(lines)):
                next_line = lines[next_line_idx]
                next_stripped = next_line.strip()

                # Check if this line is a comment continuation
                if (
                    next_stripped.startswith("#")
                    and not next_stripped.startswith("# TODO(openhands)")
                    # Skip empty comment lines
                    and next_stripped != "#"
                    # Must have content after #
                    and len(next_stripped) > 1
                ):
                    # Extract comment content (remove # and leading whitespace)
                    comment_content = next_stripped[1:].strip()

                    # Stop if we encounter a comment that looks like a
                    # separate comment (starts with capital letter and doesn't
                    # continue the previous thought)
                    if (
                        comment_content
                        # Only apply this rule if we already have
                        # continuation lines
                        and continuation_lines
                        and comment_content[0].isupper()
                        and not comment_content.lower().startswith(
                            (
                                "and ",
                                "or ",
                                "but ",
                                "when ",
                                "that ",
                                "which ",
                                "where ",
                            )
                        )
                    ):
                        break

                    if comment_content:  # Only add non-empty content
                        continuation_lines.append(comment_content)
                        full_text += " " + comment_content
                elif next_stripped == "#":
                    # Empty comment line - continue looking
                    continue
                else:
                    # Stop at first non-comment line
                    break

            # Combine description with continuation lines
            if continuation_lines:
                if description:
                    full_description = description + " " + " ".join(continuation_lines)  # noqa: E501
                else:
                    full_description = " ".join(continuation_lines)
            else:
                full_description = description

            todo_item = {
                "file": str(file_path),
                "line": line_num,
                "text": full_text,
                "description": full_description,
            }
            todos.append(todo_item)
            logger.info(f"Found TODO in {file_path}:{line_num}: {full_description}")  # noqa: E501

    if todos:
        logger.info(f"Found {len(todos)} TODO(s) in {file_path}")
    return todos


def scan_directory(directory: Path) -> list[dict]:
    """Recursively scan a directory for TODO(openhands) comments."""
    logger.info(f"Scanning directory: {directory}")
    all_todos = []

    for root, dirs, files in os.walk(directory):
        # Skip hidden and common ignore directories
        dirs[:] = [
            d
            for d in dirs
            if not d.startswith(".")
            and d
            not in {
                "__pycache__",
                "node_modules",
                ".venv",
                "venv",
                "build",
                "dist",
            }
        ]

        for file in files:
            file_path = Path(root) / file
            todos = scan_file_for_todos(file_path)
            all_todos.extend(todos)

    return all_todos


def main():
    """Main function to scan for TODOs and output results."""
    parser = argparse.ArgumentParser(
        description="Scan codebase for TODO(openhands) comments"
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Directory to scan (default: current directory)",
    )
    parser.add_argument("--output", "-o", help="Output file (default: stdout)")

    args = parser.parse_args()

    path = Path(args.directory)
    if not path.exists():
        logger.error(f"Path '{path}' does not exist")
        return 1

    if path.is_file():
        logger.info(f"Starting TODO scan on file: {path}")
        todos = scan_file_for_todos(path)
    else:
        logger.info(f"Starting TODO scan in directory: {path}")
        todos = scan_directory(path)
    logger.info(f"Scan complete. Found {len(todos)} total TODO(s)")
    output = json.dumps(todos, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Found {len(todos)} TODO(s), written to {args.output}")
    else:
        print(output)

    return 0


if __name__ == "__main__":
    exit(main())
