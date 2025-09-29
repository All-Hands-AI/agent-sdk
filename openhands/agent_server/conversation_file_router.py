from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    File,
    HTTPException,
    Path as FastApiPath,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse

from openhands.agent_server.conversation_service import (
    get_default_conversation_service,
)
from openhands.agent_server.models import Success
from openhands.sdk.logger import get_logger


logger = get_logger(__name__)
conversation_file_router = APIRouter(tags=["Files"])
conversation_service = get_default_conversation_service()


@conversation_file_router.post("/{conversation_id}/file/upload/{path}")
async def upload_file(
    conversation_id: UUID,
    path: Annotated[
        str, FastApiPath(alias="path", description="Target path relative to workspace")
    ],
    file: UploadFile = File(...),
) -> Success:
    """Upload a file to the conversation's workspace."""
    # Get the conversation's working directory
    target_path = await _get_target_path(conversation_id, path)

    try:
        # Ensure target directory exists
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Stream the file to disk to avoid memory issues with large files
        with open(target_path, "wb") as f:
            while chunk := await file.read(8192):  # Read in 8KB chunks
                f.write(chunk)

        logger.info(f"Uploaded file to {target_path}")
        return Success()

    except Exception as e:
        logger.error(f"Failed to upload file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {str(e)}",
        )


@conversation_file_router.get("/{conversation_id}/file/download/{path}")
async def download_file(
    conversation_id: UUID,
    path: Annotated[str, FastApiPath(description="File path relative to workspace")],
) -> FileResponse:
    """Download a file from the conversation's workspace."""
    try:
        target_path = await _get_target_path(conversation_id, path)

        if not target_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
            )

        if not target_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Path is not a file"
            )

        return FileResponse(
            path=target_path,
            filename=target_path.name,
            media_type="application/octet-stream",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download file: {str(e)}",
        )


async def _get_target_path(conversation_id: UUID, path: str) -> Path:
    """Get the target path for a file operation within a conversation's workspace."""
    # Get the conversation's event service to access working_dir
    event_service = await conversation_service.get_event_service(conversation_id)
    if event_service is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    # Get the working directory from the conversation
    workspace_path = Path(event_service.stored.working_dir)
    target_path = workspace_path / path
    target_path = target_path.resolve()
    workspace_path = workspace_path.resolve()

    try:
        target_path.relative_to(workspace_path)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot access file outside conversation workspace",
        )
    return target_path
