"""Git router for OpenHands SDK."""

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, status

from openhands.sdk.git.git_changes import get_git_changes
from openhands.sdk.git.git_diff import get_git_diff
from openhands.sdk.git.models import GitChange, GitDiff
from openhands.sdk.workspace.local import LocalWorkspace


git_router = APIRouter(prefix="/git", tags=["Git"])
logger = logging.getLogger(__name__)


def _resolve_and_enforce(path: Path) -> Path:
    root = LocalWorkspace.get_workspace_root()
    target = (root / path).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="path_outside_workspace_root",
        )
    return target


@git_router.get("/changes/{path:path}")
async def git_changes(
    path: Path,
) -> list[GitChange]:
    loop = asyncio.get_running_loop()
    target = _resolve_and_enforce(path)
    changes = await loop.run_in_executor(None, get_git_changes, target)
    return changes


# bash event routes
@git_router.get("/diff/{path:path}")
async def git_diff(
    path: Path,
) -> GitDiff:
    loop = asyncio.get_running_loop()
    target = _resolve_and_enforce(path)
    diff = await loop.run_in_executor(None, get_git_diff, target)
    return diff
