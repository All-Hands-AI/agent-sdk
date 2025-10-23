#!/usr/bin/env python3
"""Get git changes in the current working directory relative to the remote origin
if possible.
"""

import glob
import json
import os
from pathlib import Path

from openhands.sdk.git.models import GitChange, GitChangeStatus
from openhands.sdk.git.utils import get_valid_ref, run


def _map_git_status_to_enum(status: str) -> GitChangeStatus:
    """Map git status codes to GitChangeStatus enum values."""
    status_mapping = {
        "M": GitChangeStatus.UPDATED,
        "A": GitChangeStatus.ADDED,
        "D": GitChangeStatus.DELETED,
        "U": GitChangeStatus.UPDATED,  # Unmerged files are treated as updated
    }
    if status not in status_mapping:
        raise ValueError(f"Unknown git status: {status}")
    return status_mapping[status]


def get_changes_in_repo(repo_dir: str | Path) -> list[GitChange]:
    # Gets the status relative to the origin default branch
    # Not the same as `git status`

    ref = get_valid_ref(repo_dir)
    if not ref:
        return []

    # Get changed files
    changed_files = run(
        f"git --no-pager diff --name-status {ref}", repo_dir
    ).splitlines()
    changes = []
    for line in changed_files:
        if not line.strip():
            raise RuntimeError(f"unexpected_value_in_git_diff:{changed_files}")

        # Handle different output formats from git diff --name-status
        # Depending on git config, format can be either:
        # * "A file.txt"
        # * "A       file.txt"
        # * "R100    old_file.txt    new_file.txt" (rename with similarity percentage)
        parts = line.split()
        if len(parts) < 2:
            raise RuntimeError(f"unexpected_value_in_git_diff:{changed_files}")

        status = parts[0].strip()

        # Handle rename operations (status starts with 'R' followed
        # by similarity percentage)
        if status.startswith("R") and len(parts) == 3:
            # Rename: convert to delete (old path) + add (new path)
            old_path = parts[1].strip()
            new_path = parts[2].strip()
            changes.append(
                GitChange(
                    status=GitChangeStatus.DELETED,
                    path=Path(old_path),
                )
            )
            changes.append(
                GitChange(
                    status=GitChangeStatus.ADDED,
                    path=Path(new_path),
                )
            )
            continue

        # Handle copy operations (status starts with 'C' followed by
        # similarity percentage)
        elif status.startswith("C") and len(parts) == 3:
            # Copy: only add the new path (original remains)
            new_path = parts[2].strip()
            changes.append(
                GitChange(
                    status=GitChangeStatus.ADDED,
                    path=Path(new_path),
                )
            )
            continue

        # Handle regular operations (M, A, D, etc.)
        elif len(parts) == 2:
            path = parts[1].strip()
        else:
            raise RuntimeError(f"unexpected_value_in_git_diff:{changed_files}")

        if status == "??":
            status = "A"
        elif status == "*":
            status = "M"

        # Check for valid single-character status codes
        if status in {"M", "A", "D", "U"}:
            changes.append(
                GitChange(
                    status=_map_git_status_to_enum(status),
                    path=Path(path),
                )
            )
        else:
            raise RuntimeError(f"unexpected_status_in_git_diff:{changed_files}")

    # Get untracked files
    untracked_files = run(
        "git --no-pager ls-files --others --exclude-standard", repo_dir
    ).splitlines()
    for path in untracked_files:
        if path:
            changes.append(
                GitChange(
                    status=GitChangeStatus.ADDED,
                    path=Path(path),
                )
            )

    return changes


def get_git_changes(cwd: str | Path) -> list[GitChange]:
    git_dirs = {
        os.path.dirname(f)[2:]
        for f in glob.glob("./*/.git", root_dir=cwd, recursive=True)
    }

    # First try the workspace directory
    changes = get_changes_in_repo(cwd)

    # Filter out any changes which are in one of the git directories
    changes = [
        change
        for change in changes
        if next(
            iter(
                git_dir for git_dir in git_dirs if str(change.path).startswith(git_dir)
            ),
            None,
        )
        is None
    ]

    # Add changes from git directories
    for git_dir in git_dirs:
        git_dir_changes = get_changes_in_repo(str(Path(cwd, git_dir)))
        for change in git_dir_changes:
            # Create a new GitChange with the updated path
            updated_change = GitChange(
                status=change.status,
                path=Path(git_dir) / change.path,
            )
            changes.append(updated_change)

    changes.sort(key=lambda change: str(change.path))

    return changes


if __name__ == "__main__":
    try:
        changes = get_git_changes(os.getcwd())
        # Convert GitChange objects to dictionaries for JSON serialization
        changes_dict = [
            {
                "status": change.status.value,
                "path": str(change.path),
            }
            for change in changes
        ]
        print(json.dumps(changes_dict))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
