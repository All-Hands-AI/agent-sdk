"""Git router for OpenHands SDK."""

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, Depends

from openhands.agent_server.dependencies import get_event_service
from openhands.agent_server.event_service import EventService
from openhands.sdk.git.models import GitChange, GitDiff


git_router = APIRouter(prefix="/git", tags=["Git"])
logger = logging.getLogger(__name__)


@git_router.get("{conversation_id}/changes")
async def git_changes(
    path: Path,
    event_service: EventService = Depends(get_event_service),
) -> list[GitChange]:
    workspace = event_service.get_conversation().workspace
    loop = asyncio.get_running_loop()
    changes = await loop.run_in_executor(None, workspace.git_changes, path)
    return changes


# bash event routes
@git_router.get("{conversation_id}/diff/{path:path}")
async def git_diff(
    path: Path,
    event_service: EventService = Depends(get_event_service),
) -> GitDiff:
    workspace = event_service.get_conversation().workspace
    loop = asyncio.get_running_loop()
    changes = await loop.run_in_executor(None, workspace.git_diff, path)
    return changes
