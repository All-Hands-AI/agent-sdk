"""Command router for OpenHands SDK."""

import logging
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter

from openhands.agent_server.bash_service import get_default_bash_event_service
from openhands.agent_server.conversation_service import get_default_conversation_service
from openhands.sdk.git.git_changes import get_git_changes
from openhands.sdk.git.git_diff import get_git_diff
from openhands.sdk.git.models import GitChange


git_router = APIRouter(prefix="/git", tags=["Git"])
logger = logging.getLogger(__name__)
bash_event_service = get_default_bash_event_service()
conversation_service = get_default_conversation_service()

# TODO: Ditch the dict - use classes
# Maybe make this "git" rather than "command"

# Is it something


@git_router.get("/changes/{conversation_id}")
async def git_changes(
    conversation_id: UUID,
) -> list[GitChange]:
    conversation_info = await conversation_service.get_conversation(conversation_id)
    assert conversation_info is not None
    return get_git_changes(conversation_info.workspace.working_dir)


# bash event routes
@git_router.get("/diff/{conversation_id}/{path:path}")
async def git_diff(
    conversation_id: UUID,
    path: str,
) -> dict[str, str]:
    conversation_info = await conversation_service.get_conversation(conversation_id)
    assert conversation_info is not None
    file_path = Path(conversation_info.workspace.working_dir) / path
    result = get_git_diff(str(file_path))
    return result


"""
@git_router.get("/cmd/download-trajectory/{conversation_id}")
async def download_trajectory(
    conversation_id: UUID,
) -> FileResponse:
    config = get_default_config()
    temp_file = Path(tempfile.gettempdir()) / f"{conversation_id.hex}.zip"
    conversation_dir = config.conversations_path / conversation_id.hex
    _, task = await bash_event_service.start_bash_command(
        ExecuteBashRequest(command=f"zip -r {temp_file} {conversation_dir}")
    )
    await task
    return FileResponse(
        path=temp_file,
        filename=temp_file.name,
        media_type="application/octet-stream",
        background=BackgroundTask(temp_file.unlink),
    )
"""
