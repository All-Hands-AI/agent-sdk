"""VSCode router for agent server API endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from openhands.agent_server.vscode_service import get_vscode_service
from openhands.sdk.logger import get_logger


logger = get_logger(__name__)

vscode_router = APIRouter(prefix="/vscode", tags=["vscode"])


class VSCodeTokenResponse(BaseModel):
    """Response model for VSCode connection token."""

    token: str | None


class VSCodeUrlResponse(BaseModel):
    """Response model for VSCode URL."""

    url: str | None
    token: str | None


@vscode_router.get("/connection_token", response_model=VSCodeTokenResponse)
async def get_vscode_connection_token() -> VSCodeTokenResponse:
    """Get the VSCode connection token.

    Returns:
        VSCode connection token if available, None otherwise
    """
    try:
        vscode_service = get_vscode_service()
        token = vscode_service.get_connection_token()
        return VSCodeTokenResponse(token=token)
    except Exception as e:
        logger.error(f"Error getting VSCode connection token: {e}")
        raise HTTPException(status_code=500, detail="Failed to get VSCode token")


@vscode_router.get("/url", response_model=VSCodeUrlResponse)
async def get_vscode_url(base_url: str = "http://localhost") -> VSCodeUrlResponse:
    """Get the VSCode URL with authentication token.

    Args:
        base_url: Base URL for the VSCode server (default: http://localhost)

    Returns:
        VSCode URL with token if available, None otherwise
    """
    try:
        vscode_service = get_vscode_service()
        token = vscode_service.get_connection_token()
        url = vscode_service.get_vscode_url(base_url) if token else None
        return VSCodeUrlResponse(url=url, token=token)
    except Exception as e:
        logger.error(f"Error getting VSCode URL: {e}")
        raise HTTPException(status_code=500, detail="Failed to get VSCode URL")


@vscode_router.get("/status")
async def get_vscode_status() -> dict[str, bool]:
    """Get the VSCode server status.

    Returns:
        Dictionary with running status
    """
    try:
        vscode_service = get_vscode_service()
        return {"running": vscode_service.is_running()}
    except Exception as e:
        logger.error(f"Error getting VSCode status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get VSCode status")
