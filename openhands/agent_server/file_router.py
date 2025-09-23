from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    File,
    HTTPException,
    Path as FastApiPath,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse

from openhands.agent_server.config import get_default_config
from openhands.agent_server.models import Success
from openhands.sdk.logger import get_logger


logger = get_logger(__name__)
file_router = APIRouter(prefix="/file", tags=["Files"])
config = get_default_config()


@file_router.post("/upload/{path}")
async def upload_file(
    path: Annotated[
        str, FastApiPath(alias="path", description="Target path relative to workspace")
    ],
    file: UploadFile = File(...),
) -> Success:
    """Upload a file to the workspace."""
    # Determine target path
    target_path = _get_target_path(path)

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


@file_router.get("/download/{path}")
async def download_file(
    path: Annotated[str, FastApiPath(description="File path relative to workspace")],
) -> FileResponse:
    """Download a file from the workspace."""
    try:
        target_path = _get_target_path(path)

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


def _get_target_path(path: str) -> Path:
    # Get the target path from the variable given, making sure it
    # is within the workspace
    target_path = config.workspace_path / path
    target_path = target_path.resolve()
    workspace_path = config.workspace_path.resolve()
    try:
        target_path.relative_to(workspace_path)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot upload file outside workspace",
        )
    return target_path
