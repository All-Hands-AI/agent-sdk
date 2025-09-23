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

from openhands.agent_server.bash_task_service import get_default_bash_task_service
from openhands.agent_server.models import TaskEvent, TaskEventPage
from openhands.agent_server.pub_sub import Subscriber
from openhands.sdk.event.base import EventBase
from openhands.sdk.preset.default import register_default_tools
from openhands.sdk.tool.registry import list_registered_tools
from openhands.tools.execute_bash.definition import ExecuteBashAction


tool_router = APIRouter(prefix="/tools", tags=["Tools"])
bash_task_service = get_default_bash_task_service()
logger = logging.getLogger(__name__)
register_default_tools(enable_browser=True)


# Tool listing
@tool_router.get("/")
async def list_available_tools() -> list[str]:
    """List all available tools."""
    tools = list_registered_tools()
    return tools


# Bash task routes
@tool_router.get("/bash_tasks/search")
async def search_bash_tasks(
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
) -> TaskEventPage:
    """Search / List bash task events"""
    assert limit > 0
    assert limit <= 100
    return await bash_task_service.search_events(action_id, page_id, limit)


@tool_router.get(
    "/bash_tasks/{event_id}", responses={404: {"description": "Item not found"}}
)
async def get_bash_task_event(event_id: str) -> TaskEvent:
    """Get a bash task event given an id"""
    event = await bash_task_service.get_event(event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return event


@tool_router.get("/bash_tasks/")
async def batch_get_bash_task_events(
    event_ids: list[str],
) -> list[TaskEvent | None]:
    """Get a batch of bash task events given their ids, returning null for any
    missing item."""
    events = await bash_task_service.batch_get_events(event_ids)
    return events


@tool_router.post("/bash_tasks/")
async def start_bash_task(action: ExecuteBashAction) -> TaskEvent:
    """Start a bash task execution"""
    action_event = await bash_task_service.start_bash_task(action)
    return action_event


# WebSocket for bash task events
@tool_router.websocket("/bash_tasks/socket")
async def bash_task_socket(websocket: WebSocket):
    await websocket.accept()
    subscriber_id = await bash_task_service.subscribe_to_events(
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
                logger.exception("error_in_bash_task_subscription", stack_info=True)
                # For critical errors that indicate the websocket is broken, exit
                if isinstance(e, (RuntimeError, ConnectionError)):
                    raise
                # For other exceptions, continue the loop
    finally:
        await bash_task_service.unsubscribe_from_events(subscriber_id)


@dataclass
class _WebSocketSubscriber(Subscriber):
    websocket: WebSocket

    async def __call__(self, event: EventBase):
        try:
            dumped = event.model_dump()
            await self.websocket.send_json(dumped)
        except Exception:
            logger.exception("error_sending_bash_task_event:{event}", stack_info=True)
