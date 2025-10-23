"""Command router for OpenHands SDK."""

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter

from openhands.agent_server.config import get_default_config
from openhands.sdk.git.models import GitChange, GitDiff
from openhands.sdk.workspace.local import LocalWorkspace


git_router = APIRouter(prefix="/git", tags=["Git"])
logger = logging.getLogger(__name__)
config = get_default_config()


@git_router.get("/changes/{path:path}")
async def git_changes(
    path: Path,
) -> list[GitChange]:
    workspace = LocalWorkspace(working_dir=str(config.working_dir))
    loop = asyncio.get_running_loop()
    changes = await loop.run_in_executor(None, workspace.git_changes, path)
    return changes


# bash event routes
@git_router.get("/diff/{path:path}")
async def git_diff(
    path: str,
) -> GitDiff:
    workspace = LocalWorkspace(working_dir=str(config.working_dir))
    loop = asyncio.get_running_loop()
    diff = await loop.run_in_executor(None, workspace.git_diff, path)
    return diff
