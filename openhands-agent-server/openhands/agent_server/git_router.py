"""Git router for OpenHands SDK."""

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
workspace = LocalWorkspace(working_dir=str(config.working_dir))


@git_router.get("/changes/{path:path}")
async def git_changes(
    path: Path,
) -> list[GitChange]:
    assert (
        (config.working_dir / path)
        .resolve()
        .is_relative_to(config.working_dir.resolve())
    )
    loop = asyncio.get_running_loop()
    changes = await loop.run_in_executor(None, workspace.git_changes, path)
    return changes


# bash event routes
@git_router.get("/diff/{path:path}")
async def git_diff(
    path: Path,
) -> GitDiff:
    assert (
        (config.working_dir / path)
        .resolve()
        .is_relative_to(config.working_dir.resolve())
    )
    loop = asyncio.get_running_loop()
    diff = await loop.run_in_executor(None, workspace.git_diff, path)
    return diff
