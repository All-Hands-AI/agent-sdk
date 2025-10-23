#!/usr/bin/env python3
"""Get git diff in a single git file for the closest git repo in the file system"""

import json
import os
import sys
from pathlib import Path

from openhands.sdk.git.models import GitDiff
from openhands.sdk.git.utils import get_valid_ref, run


MAX_FILE_SIZE_FOR_GIT_DIFF = 1024 * 1024  # 1 Mb


def get_closest_git_repo(path: Path) -> Path | None:
    while True:
        path = path.parent
        git_path = Path(path, ".git")
        if git_path.is_dir():
            return path
        if path.parent == path:
            return None


def get_git_diff(relative_file_path: str | Path) -> GitDiff:
    path = Path(os.getcwd(), relative_file_path).resolve()
    if os.path.getsize(path) > MAX_FILE_SIZE_FOR_GIT_DIFF:
        raise ValueError("file_to_large")
    closest_git_repo = get_closest_git_repo(path)
    if not closest_git_repo:
        raise ValueError("no_repository")
    current_rev = get_valid_ref(str(closest_git_repo))
    try:
        original = run(
            f'git show "{current_rev}:{path.relative_to(closest_git_repo)}"',
            str(closest_git_repo),
        )
    except RuntimeError:
        original = ""
    try:
        with open(path) as f:
            modified = "\n".join(f.read().splitlines())
    except FileNotFoundError:
        modified = ""
    return GitDiff(
        modified=modified,
        original=original,
    )


if __name__ == "__main__":
    diff = get_git_diff(sys.argv[-1])
    print(json.dumps(diff))
