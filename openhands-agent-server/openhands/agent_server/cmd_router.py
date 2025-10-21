"""Command router for OpenHands SDK."""

import logging
from uuid import UUID

from fastapi import APIRouter


cmd_router = APIRouter(prefix="/cmd", tags=["Command"])
logger = logging.getLogger(__name__)


@cmd_router.get("/cmd/git-changes/{conversation_id}")
async def git_changes(
    conversation_id: UUID,
) -> str:
    raise NotImplementedError()


# bash event routes
@cmd_router.get("/cmd/git-diff/{conversation_id}")
async def git_diff(
    conversation_id: UUID,
) -> str:
    raise NotImplementedError()


@cmd_router.get("/cmd/download-trajectory/{conversation_id}")
async def download_trajectory(
    conversation_id: UUID,
) -> str:
    raise NotImplementedError()
