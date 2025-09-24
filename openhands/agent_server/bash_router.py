"""Bash router for OpenHands SDK."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)

from openhands.agent_server.bash_service import get_default_bash_event_service
from openhands.agent_server.models import (
    BashCommand,
    BashEventBase,
    BashEventPage,
    BashEventSortOrder,
    ExecuteBashRequest,
)
from openhands.agent_server.pub_sub import Subscriber


bash_router = APIRouter(prefix="/bash", tags=["Bash"])
bash_event_service = get_default_bash_event_service()
logger = logging.getLogger(__name__)


# bash event routes
@bash_router.get("/bash_events/search")
async def search_bash_events(
    kind__eq: Literal["BashCommand", "BashOutput"] | None = None,
    command_id__eq: UUID | None = None,
    timestamp__gte: datetime | None = None,
    timestamp__lt: datetime | None = None,
    sort_order: BashEventSortOrder = BashEventSortOrder.TIMESTAMP,
    page_id: Annotated[
        str | None,
        Query(title="Optional next_page_id from the previously returned page"),
    ] = None,
    limit: Annotated[
        int,
        Query(title="The max number of results in the page", gt=0, lte=100),
    ] = 100,
) -> BashEventPage:
    """Search / List bash event events"""
    assert limit > 0
    assert limit <= 100

    return await bash_event_service.search_bash_events(
        kind__eq=kind__eq,
        command_id__eq=command_id__eq,
        timestamp__gte=timestamp__gte,
        timestamp__lt=timestamp__lt,
        sort_order=sort_order,
        page_id=page_id,
        limit=limit,
    )


@bash_router.get(
    "/bash_events/{event_id}", responses={404: {"description": "Item not found"}}
)
async def get_bash_event(event_id: str) -> BashEventBase:
    """Get a bash event event given an id"""
    event = await bash_event_service.get_bash_event(event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return event


@bash_router.get("/bash_events/")
async def batch_get_bash_events(
    event_ids: list[str],
) -> list[BashEventBase | None]:
    """Get a batch of bash event events given their ids, returning null for any
    missing item."""
    events = await bash_event_service.batch_get_bash_events(event_ids)
    return events


@bash_router.post("/execute_bash_command")
async def start_bash_command(request: ExecuteBashRequest) -> BashCommand:
    """Execute a bash command"""
    command, _ = await bash_event_service.start_bash_command(request)
    return command


@bash_router.delete("/bash_events")
async def clear_all_bash_events() -> dict[str, int]:
    """Clear all bash events from storage"""
    count = await bash_event_service.clear_all_events()
    return {"cleared_count": count}


# WebSocket for bash events
@bash_router.websocket("/bash_events/socket")
async def bash_event_socket(websocket: WebSocket):
    await websocket.accept()
    subscriber_id = await bash_event_service.subscribe_to_events(
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
                logger.exception("error_in_bash_event_subscription", stack_info=True)
                # For critical errors that indicate the websocket is broken, exit
                if isinstance(e, (RuntimeError, ConnectionError)):
                    raise
                # For other exceptions, continue the loop
    finally:
        await bash_event_service.unsubscribe_from_events(subscriber_id)


@dataclass
class _WebSocketSubscriber(Subscriber[BashEventBase]):
    websocket: WebSocket

    async def __call__(self, event: BashEventBase):
        try:
            dumped = event.model_dump()
            await self.websocket.send_json(dumped)
        except Exception:
            logger.exception("error_sending_bash_event:{event}", stack_info=True)
