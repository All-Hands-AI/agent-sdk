"""
Workspace router for file operations and bash command execution.
"""

from dataclasses import dataclass
from typing import Annotated

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import FileResponse
from fastapi.websockets import WebSocketState

from openhands.agent_server.config import get_default_config
from openhands.agent_server.models import (
    BashEventPage,
    Success,
)
from openhands.agent_server.pub_sub import Subscriber
from openhands.agent_server.workspace_service import (
    BashEvent,
    get_default_workspace_service,
)
from openhands.sdk.logger import get_logger
from openhands.tools.execute_bash import ExecuteBashAction, ExecuteBashObservation


logger = get_logger(__name__)
router = APIRouter(prefix="/api/workspace")
workspace_service = get_default_workspace_service()
config = get_default_config()


# File operations


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    path_query: Annotated[
        str | None, Query(alias="path", description="Target path relative to workspace")
    ] = None,
    path_form: Annotated[
        str | None, Form(alias="path", description="Target path relative to workspace")
    ] = None,
) -> Success:
    """Upload a file to the workspace."""
    # Determine target path (prefer form data over query parameter)
    path = path_form or path_query
    if path:
        target_path = config.workspace_path / path
    else:
        filename = file.filename or "uploaded_file"
        target_path = config.workspace_path / filename

    # Security check: ensure the resolved path is within workspace
    target_path = target_path.resolve()
    workspace_path = config.workspace_path.resolve()
    try:
        target_path.relative_to(workspace_path)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot upload file outside workspace",
        )

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


@router.get("/download")
async def download_file(
    path: Annotated[str, Query(description="File path relative to workspace")],
) -> FileResponse:
    """Download a file from the workspace."""
    try:
        file_path = config.workspace_path / path

        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
            )

        if not file_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Path is not a file"
            )

        # Check if file is within workspace (security check)
        try:
            file_path.resolve().relative_to(config.workspace_path.resolve())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot access file outside workspace",
            )

        return FileResponse(
            path=file_path,
            filename=file_path.name,
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


# Bash command execution


@router.post("/execute")
async def execute_bash_command(request: ExecuteBashAction) -> ExecuteBashObservation:
    """Execute a bash command in the workspace."""
    try:
        observation = await workspace_service.execute_bash_command(request)
        return observation

    except Exception as e:
        logger.error(f"Failed to execute bash command: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute bash command: {str(e)}",
        )


# Bash events


@router.get("/bash-events/search")
async def search_bash_events(
    page_id: Annotated[
        str | None,
        Query(description="Optional next_page_id from the previously returned page"),
    ] = None,
    limit: Annotated[
        int, Query(description="Maximum number of events to return", gt=0, le=100)
    ] = 100,
    command_filter: Annotated[
        str | None, Query(description="Filter by command content")
    ] = None,
) -> BashEventPage:
    """Search bash command execution events."""
    try:
        # Convert page_id to offset for the service layer
        offset = int(page_id) if page_id and page_id.isdigit() else 0

        events = workspace_service.search_events(
            limit=limit,
            offset=offset,
            command_filter=command_filter,
        )

        # Create discriminated union items (actions and observations)
        items = []
        for event in events:
            # Add the action
            items.append(event.action)
            # Add the observation if it exists
            if event.observation:
                items.append(event.observation)

        # Calculate next_page_id
        next_page_id = str(offset + limit) if len(events) == limit else None

        return BashEventPage(
            items=items,
            next_page_id=next_page_id,
        )

    except Exception as e:
        logger.error(f"Failed to search bash events: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search bash events: {str(e)}",
        )


@router.get("/bash-events/{event_id}")
async def get_bash_event(event_id: str) -> BashEvent:
    """Get a specific bash event by ID."""
    try:
        event = workspace_service.get_event(event_id)

        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
            )

        return event

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get bash event: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get bash event: {str(e)}",
        )


@router.get("/bash-events/count")
async def count_bash_events(
    command_filter: Annotated[
        str | None, Query(description="Filter by command content")
    ] = None,
) -> int:
    """Count bash command execution events."""
    try:
        return workspace_service.count_events(command_filter=command_filter)

    except Exception as e:
        logger.error(f"Failed to count bash events: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to count bash events: {str(e)}",
        )


# WebSocket for real-time bash events


@router.websocket("/bash-events/socket")
async def bash_events_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time bash event streaming."""
    await websocket.accept()

    subscriber_id = await workspace_service.subscribe_to_events(
        _WebSocketBashEventSubscriber(websocket)
    )

    try:
        while websocket.application_state == WebSocketState.CONNECTED:
            try:
                # Keep the connection alive and handle any incoming messages
                await websocket.receive_text()
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error in bash events websocket: {e}")
                break
    finally:
        await workspace_service.unsubscribe_from_events(subscriber_id)


@dataclass
class _WebSocketBashEventSubscriber(Subscriber):
    """WebSocket subscriber for bash events."""

    websocket: WebSocket

    async def __call__(self, event):
        """Send bash event to WebSocket client."""
        try:
            # Only handle BashEvent instances
            if not isinstance(event, BashEvent):
                return

            await self.websocket.send_json(event.model_dump())
        except Exception as e:
            logger.error(f"Error sending bash event to websocket: {e}")
