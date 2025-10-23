"""Command router for OpenHands SDK."""

import logging
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter

from openhands.agent_server.bash_service import get_default_bash_event_service
from openhands.agent_server.conversation_service import get_default_conversation_service
from openhands.sdk.git.git_changes import get_git_changes
from openhands.sdk.git.git_diff import get_git_diff
from openhands.sdk.git.models import GitChange, GitDiff


git_router = APIRouter(prefix="/git", tags=["Git"])
logger = logging.getLogger(__name__)
bash_event_service = get_default_bash_event_service()
conversation_service = get_default_conversation_service()


@git_router.get("/changes/{path:path}")
async def git_changes(
    path: Path,
) -> list[GitChange]:
    return get_git_changes(path)


# bash event routes
@git_router.get("/diff/{conversation_id}/{path:path}")
async def git_diff(
    conversation_id: UUID,
    path: str,
) -> GitDiff:
    conversation_info = await conversation_service.get_conversation(conversation_id)
    assert conversation_info is not None
    file_path = Path(conversation_info.workspace.working_dir) / path
    result = get_git_diff(str(file_path))
    return result
