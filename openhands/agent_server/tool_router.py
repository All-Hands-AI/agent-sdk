"""Tool router for OpenHands SDK."""

import logging
from dataclasses import dataclass
from typing import Annotated

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)

from openhands.agent_server.models import ToolEvent, ToolEventPage
from openhands.agent_server.pub_sub import Subscriber
from openhands.agent_server.tool_event_service import get_default_tool_event_service
from openhands.sdk.event.base import EventBase
from openhands.sdk.preset.default import register_default_tools
from openhands.sdk.tool.registry import list_registered_tools
from openhands.tools.execute_bash.definition import ExecuteBashAction


tool_router = APIRouter(prefix="/tools", tags=["Tools"])
tool_event_service = get_default_tool_event_service()
logger = logging.getLogger(__name__)
register_default_tools(enable_browser=True)


# Tool listing
@tool_router.get("/")
async def list_available_tools() -> list[str]:
    """List all available tools."""
    tools = list_registered_tools()
    return tools


# tool event routes
@tool_router.get("/tool_events/search")
async def search_tool_events(
    action_id: Annotated[
        str | None,
        Query(title="Optional action ID to filter observations for a specific action"),
    ] = None,
    page_id: Annotated[
        str | None,
        Query(title="Optional next_page_id from the previously returned page"),
    ] = None,
    limit: Annotated[
        int,
        Query(title="The max number of results in the page", gt=0, lte=100),
    ] = 100,
) -> ToolEventPage:
    """Search / List tool event events"""
    assert limit > 0
    assert limit <= 100
    return await tool_event_service.search_events(action_id, page_id, limit)


@tool_router.get(
    "/tool_events/{event_id}", responses={404: {"description": "Item not found"}}
)
async def get_tool_event(event_id: str) -> ToolEvent:
    """Get a tool event event given an id"""
    event = await tool_event_service.get_event(event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return event


@tool_router.get("/tool_events/")
async def batch_get_tool_events(
    event_ids: list[str],
) -> list[ToolEvent | None]:
    """Get a batch of tool event events given their ids, returning null for any
    missing item."""
    events = await tool_event_service.batch_get_events(event_ids)
    return events


@tool_router.post("/tool_events/")
async def start_bash_execution(action: ExecuteBashAction) -> ToolEvent:
    """Start a tool event execution"""
    action_event = await tool_event_service.start_bash_execution(action)
    return action_event


# WebSocket for tool events
@tool_router.websocket("/tool_events/socket")
async def tool_event_socket(websocket: WebSocket):
    await websocket.accept()
    subscriber_id = await tool_event_service.subscribe_to_events(
        _WebSocketSubscriber(websocket)
    )
    try:
        while True:
            try:
                # Keep the connection alive and handle any incoming messages
                await websocket.receive_text()
            except WebSocketDisconnect:
                # Exit the loop when websocket disconnects
                return
            except Exception as e:
                logger.exception("error_in_tool_event_subscription", stack_info=True)
                # For critical errors that indicate the websocket is broken, exit
                if isinstance(e, (RuntimeError, ConnectionError)):
                    raise
                # For other exceptions, continue the loop
    finally:
        await tool_event_service.unsubscribe_from_events(subscriber_id)


@dataclass
class _WebSocketSubscriber(Subscriber):
    websocket: WebSocket

    async def __call__(self, event: EventBase):
        try:
            dumped = event.model_dump()
            await self.websocket.send_json(dumped)
        except Exception:
            logger.exception("error_sending_tool_event:{event}", stack_info=True)
