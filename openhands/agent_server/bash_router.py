"""Bash router for OpenHands SDK."""

import logging
from dataclasses import dataclass
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
    Success,
)
from openhands.agent_server.pub_sub import Subscriber
from openhands.sdk.event.base import EventBase


bash_router = APIRouter(prefix="/bash", tags=["Bash"])
bash_event_service = get_default_bash_event_service()
logger = logging.getLogger(__name__)


# bash event routes
@bash_router.get("/bash_events/search")
async def search_bash_events(
    action_id: Annotated[
        str | None,
        Query(title="Optional action ID to filter events for a specific action"),
    ] = None,
    kind: Annotated[
        Literal["bashcommand", "bashoutput"] | None,
        Query(title="Optional event kind filter (bashcommand or bashoutput)"),
    ] = None,
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

    # Convert action_id string to UUID if provided
    action_id_uuid = None
    if action_id:
        try:
            action_id_uuid = UUID(action_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid UUID format for action_id: {action_id}",
            )

    return await bash_event_service.search_events(
        kind__eq=kind, action_id__eq=action_id_uuid, page_id=page_id, limit=limit
    )


@bash_router.get(
    "/bash_events/{event_id}", responses={404: {"description": "Item not found"}}
)
async def get_bash_event(event_id: str) -> BashEventBase:
    """Get a bash event event given an id"""
    event = await bash_event_service.get_event(event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return event


@bash_router.get("/bash_events/")
async def batch_get_bash_events(
    event_ids: list[str],
) -> list[BashEventBase | None]:
    """Get a batch of bash event events given their ids, returning null for any
    missing item."""
    events = await bash_event_service.batch_get_events(event_ids)
    return events


@bash_router.post("/execute_bash_command")
async def execute_bash_command(action: BashCommand) -> Success:
    """Execute a bash command"""
    await bash_event_service.start_bash_command(action)
    return Success()


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
class _WebSocketSubscriber(Subscriber):
    websocket: WebSocket

    async def __call__(self, event: EventBase):
        try:
            dumped = event.model_dump()
            await self.websocket.send_json(dumped)
        except Exception:
            logger.exception("error_sending_bash_event:{event}", stack_info=True)
