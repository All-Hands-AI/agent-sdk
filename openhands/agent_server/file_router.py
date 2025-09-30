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
    path: Annotated[str, FastApiPath(alias="path", description="Absolute file path.")],
    file: UploadFile = File(...),
) -> Success:
    """Upload a file to the workspace."""
    try:
        target_path = Path(path)
        if not target_path.is_absolute():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Path must be absolute",
            )

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
    path: Annotated[str, FastApiPath(description="Absolute file path.")],
) -> FileResponse:
    """Download a file from the workspace."""
    try:
        target_path = Path(path)
        if not target_path.is_absolute():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Path must be absolute",
            )

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
