"""Command router for OpenHands SDK."""

import logging
import tempfile
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from openhands.agent_server.bash_service import get_default_bash_event_service
from openhands.agent_server.config import get_default_config
from openhands.agent_server.conversation_service import get_default_conversation_service
from openhands.agent_server.models import ExecuteBashRequest
from openhands.sdk.cmd.git_changes import get_git_changes
from openhands.sdk.cmd.git_diff import get_git_diff


cmd_router = APIRouter(prefix="/cmd", tags=["Command"])
logger = logging.getLogger(__name__)
bash_event_service = get_default_bash_event_service()
conversation_service = get_default_conversation_service()


@cmd_router.get("/cmd/git-changes/{conversation_id}")
async def git_changes(
    conversation_id: UUID,
) -> list[dict[str, str]]:
    conversation_info = await conversation_service.get_conversation(conversation_id)
    assert conversation_info is not None
    result = get_git_changes(conversation_info.workspace.working_dir)
    return result


# bash event routes
@cmd_router.get("/cmd/git-diff/{conversation_id}/{path:path}")
async def git_diff(
    conversation_id: UUID,
    path: str,
) -> dict[str, str]:
    conversation_info = await conversation_service.get_conversation(conversation_id)
    assert conversation_info is not None
    file_path = Path(conversation_info.workspace.working_dir) / path
    result = get_git_diff(str(file_path))
    return result


@cmd_router.get("/cmd/download-trajectory/{conversation_id}")
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
