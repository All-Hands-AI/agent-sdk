"""VSCode router for conversation-specific agent server API endpoints."""

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from openhands.agent_server.conversation_service import (
    get_default_conversation_service,
)
from openhands.agent_server.vscode_service import VSCodeService
from openhands.sdk.logger import get_logger


logger = get_logger(__name__)

conversation_vscode_router = APIRouter(tags=["VSCode"])
conversation_service = get_default_conversation_service()

# Store conversation-specific VSCode services
_conversation_vscode_services: dict[UUID, VSCodeService] = {}


class VSCodeUrlResponse(BaseModel):
    """Response model for VSCode URL."""

    url: str | None


@conversation_vscode_router.get(
    "/{conversation_id}/vscode/url", response_model=VSCodeUrlResponse
)
async def get_conversation_vscode_url(
    conversation_id: UUID, base_url: str = "http://localhost:8001"
) -> VSCodeUrlResponse:
    """Get the VSCode URL with authentication token for a specific conversation.

    Args:
        conversation_id: UUID of the conversation
        base_url: Base URL for the VSCode server (default: http://localhost:8001)

    Returns:
        VSCode URL with token if available, None otherwise
    """
    vscode_service = await _get_conversation_vscode_service(conversation_id)
    if vscode_service is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "VSCode is disabled in configuration. Set enable_vscode=true to enable."
            ),
        )

    try:
        url = vscode_service.get_vscode_url(base_url)
        return VSCodeUrlResponse(url=url)
    except Exception as e:
        logger.error(
            f"Error getting VSCode URL for conversation {conversation_id}: {e}"
        )
        raise HTTPException(status_code=500, detail="Failed to get VSCode URL")


@conversation_vscode_router.get("/{conversation_id}/vscode/status")
async def get_conversation_vscode_status(
    conversation_id: UUID,
) -> dict[str, bool | str]:
    """Get the VSCode server status for a specific conversation.

    Args:
        conversation_id: UUID of the conversation

    Returns:
        Dictionary with running status and enabled status
    """
    vscode_service = await _get_conversation_vscode_service(conversation_id)
    if vscode_service is None:
        return {
            "running": False,
            "enabled": False,
            "message": "VSCode is disabled in configuration",
        }

    try:
        return {"running": vscode_service.is_running(), "enabled": True}
    except Exception as e:
        logger.error(
            f"Error getting VSCode status for conversation {conversation_id}: {e}"
        )
        raise HTTPException(status_code=500, detail="Failed to get VSCode status")


async def _get_conversation_vscode_service(
    conversation_id: UUID,
) -> VSCodeService | None:
    """Get or create a VSCode service for a specific conversation.

    Args:
        conversation_id: UUID of the conversation

    Returns:
        VSCode service instance if enabled, None if disabled
    """
    from openhands.agent_server.config import get_default_config

    config = get_default_config()

    if not config.enable_vscode:
        logger.info("VSCode is disabled in configuration")
        return None

    # Check if we already have a service for this conversation
    if conversation_id in _conversation_vscode_services:
        return _conversation_vscode_services[conversation_id]

    # Get the conversation's event service to access working_dir
    event_service = await conversation_service.get_event_service(conversation_id)
    if event_service is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found",
        )

    # Create a new VSCode service for this conversation
    workspace_path = Path(event_service.stored.working_dir)
    vscode_service = VSCodeService(
        workspace_path=workspace_path,
        port=8001,  # TODO: Consider making this configurable per conversation
        create_workspace=True,
    )

    # Start the service
    started = await vscode_service.start()
    if started:
        _conversation_vscode_services[conversation_id] = vscode_service
        logger.info(f"VSCode service started for conversation {conversation_id}")
        return vscode_service
    else:
        logger.warning(
            f"Failed to start VSCode service for conversation {conversation_id}"
        )
        return None


async def cleanup_conversation_vscode_service(conversation_id: UUID) -> None:
    """Clean up VSCode service for a conversation when it's deleted.

    Args:
        conversation_id: UUID of the conversation to clean up
    """
    if conversation_id in _conversation_vscode_services:
        vscode_service = _conversation_vscode_services[conversation_id]
        await vscode_service.stop()
        del _conversation_vscode_services[conversation_id]
        logger.info(f"VSCode service cleaned up for conversation {conversation_id}")
