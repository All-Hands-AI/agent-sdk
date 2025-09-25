"""Tool router for OpenHands SDK."""

from fastapi import APIRouter, Depends

from openhands.agent_server.dependencies import check_session_api_key_from_app
from openhands.sdk.preset.default import register_default_tools
from openhands.sdk.tool.registry import list_registered_tools


tool_router = APIRouter(prefix="/tools", tags=["Tools"])
register_default_tools(enable_browser=True)


# Tool listing
@tool_router.get("/")
async def list_available_tools(
    _: None = Depends(check_session_api_key_from_app),
) -> list[str]:
    """List all available tools."""
    tools = list_registered_tools()
    return tools
