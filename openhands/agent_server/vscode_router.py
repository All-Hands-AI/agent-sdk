"""VSCode router for agent server API endpoints."""

from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.params import Depends as DependsParam
from pydantic import BaseModel

from openhands.agent_server.dependencies import (
    get_vscode_service,
)  # re-exported name for patching in tests
from openhands.agent_server.vscode_service import VSCodeService
from openhands.sdk.logger import get_logger


logger = get_logger(__name__)

vscode_router = APIRouter(prefix="/vscode", tags=["VSCode"])


def _resolve_vscode_service(request: Request) -> VSCodeService | None:
    """Resolver that supports runtime-patched getter and app.state fallback.

    This allows tests to patch `openhands.agent_server.vscode_router.get_vscode_service`
    after route declaration and still affect dependency resolution.
    """
    getter = globals().get("get_vscode_service")
    if callable(getter):
        try:
            return getter(request)  # type: ignore[misc]
        except Exception:
            try:
                return getter()  # type: ignore[misc]
            except Exception:
                pass
    return getattr(request.app.state, "vscode_service", None)


class VSCodeUrlResponse(BaseModel):
    """Response model for VSCode URL."""

    url: str | None


@vscode_router.get("/url", response_model=VSCodeUrlResponse)
async def get_vscode_url(
    base_url: str = "http://localhost:8001",
    vscode_service: VSCodeService | None = Depends(_resolve_vscode_service),
) -> VSCodeUrlResponse:
    # Resolve for direct calls (outside FastAPI DI)
    if isinstance(vscode_service, DependsParam):  # type: ignore[unreachable]
        # In direct calls, tests patch get_vscode_service to be a zero-arg function
        # returning the mocked service. Cast to satisfy the type checker.
        try:
            getter = cast(Any, get_vscode_service)
            vscode_service = getter()
        except Exception:
            vscode_service = None
    """Get the VSCode URL with authentication token.

    Args:
        base_url: Base URL for the VSCode server (default: http://localhost:8001)

    Returns:
        VSCode URL with token if available, None otherwise
    """
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
        logger.error(f"Error getting VSCode URL: {e}")
        raise HTTPException(status_code=500, detail="Failed to get VSCode URL")


@vscode_router.get("/status")
async def get_vscode_status(
    vscode_service: VSCodeService | None = Depends(_resolve_vscode_service),
) -> dict[str, bool | str]:
    # Resolve for direct calls (outside FastAPI DI)
    if isinstance(vscode_service, DependsParam):  # type: ignore[unreachable]
        try:
            getter = cast(Any, get_vscode_service)
            vscode_service = getter()
        except Exception:
            vscode_service = None
    """Get the VSCode server status.

    Returns:
        Dictionary with running status and enabled status
    """
    if vscode_service is None:
        return {
            "running": False,
            "enabled": False,
            "message": "VSCode is disabled in configuration",
        }

    try:
        return {"running": vscode_service.is_running(), "enabled": True}
    except Exception as e:
        logger.error(f"Error getting VSCode status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get VSCode status")
