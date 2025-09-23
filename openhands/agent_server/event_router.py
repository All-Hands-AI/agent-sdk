"""
Local Event router for OpenHands SDK.
"""

import logging
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)

from openhands.agent_server.conversation_service import (
    get_default_conversation_service,
)
from openhands.agent_server.models import (
    ConfirmationResponseRequest,
    EventPage,
    EventSortOrder,
    SendMessageRequest,
    Success,
)
from openhands.agent_server.pub_sub import Subscriber
from openhands.sdk import Message
from openhands.sdk.event.base import EventBase


router = APIRouter(prefix="/conversations/{conversation_id}/events")
conversation_service = get_default_conversation_service()
logger = logging.getLogger(__name__)

# Read methods


@router.get("/search", responses={404: {"description": "Conversation not found"}})
async def search_conversation_events(
    conversation_id: UUID,
    page_id: Annotated[
        str | None,
        Query(title="Optional next_page_id from the previously returned page"),
    ] = None,
    limit: Annotated[
        int,
        Query(title="The max number of results in the page", gt=0, lte=100),
    ] = 100,
    kind: Annotated[
        str | None,
        Query(
            title="Optional filter by event kind/type (e.g., ActionEvent, MessageEvent)"
        ),
    ] = None,
    sort_order: Annotated[
        EventSortOrder,
        Query(title="Sort order for events"),
    ] = EventSortOrder.TIMESTAMP,
) -> EventPage:
    """Search / List local events"""
    assert limit > 0
    assert limit <= 100
    event_service = await conversation_service.get_event_service(conversation_id)
    if event_service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return await event_service.search_events(page_id, limit, kind, sort_order)


@router.get("/count", responses={404: {"description": "Conversation not found"}})
async def count_conversation_events(
    conversation_id: UUID,
    kind: Annotated[
        str | None,
        Query(
            title="Optional filter by event kind/type (e.g., ActionEvent, MessageEvent)"
        ),
    ] = None,
) -> int:
    """Count local events matching the given filters"""
    event_service = await conversation_service.get_event_service(conversation_id)
    if event_service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    count = await event_service.count_events(kind)
    return count


@router.get("/{event_id}", responses={404: {"description": "Item not found"}})
async def get_conversation_event(conversation_id: UUID, event_id: str) -> EventBase:
    """Get a local event given an id"""
    event_service = await conversation_service.get_event_service(conversation_id)
    if event_service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    event = await event_service.get_event(event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return event


@router.get("/")
async def batch_get_conversation_events(
    conversation_id: UUID, event_ids: list[str]
) -> list[EventBase | None]:
    """Get a batch of local events given their ids, returning null for any
    missing item."""
    event_service = await conversation_service.get_event_service(conversation_id)
    if event_service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    events = await event_service.batch_get_events(event_ids)
    return events


# Write Methods


@router.post("/")
async def send_message(conversation_id: UUID, request: SendMessageRequest) -> Success:
    """Send a message to a conversation"""
    event_service = await conversation_service.get_event_service(conversation_id)
    if event_service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    message = Message(role=request.role, content=request.content)
    await event_service.send_message(message, run=request.run)
    return Success()


@router.post(
    "/respond_to_confirmation", responses={404: {"description": "Item not found"}}
)
async def respond_to_confirmation(
    conversation_id: UUID, request: ConfirmationResponseRequest
) -> Success:
    """Accept or reject a pending action in confirmation mode."""
    event_service = await conversation_service.get_event_service(conversation_id)
    if event_service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    await event_service.respond_to_confirmation(request)
    return Success()


# Subscribers


@router.websocket("/socket")
async def socket(
    conversation_id: UUID,
    websocket: WebSocket,
):
    await websocket.accept()
    event_service = await conversation_service.get_event_service(conversation_id)
    if event_service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    subscriber_id = await event_service.subscribe_to_events(
        _WebSocketSubscriber(websocket)
    )
    try:
        while True:
            try:
                data = await websocket.receive_json()
                message = Message.model_validate(data)
                await event_service.send_message(message, run=True)
            except WebSocketDisconnect:
                # Exit the loop when websocket disconnects
                return
            except Exception as e:
                logger.exception("error_in_subscription", stack_info=True)
                # For critical errors that indicate the websocket is broken, exit
                if isinstance(e, (RuntimeError, ConnectionError)):
                    raise
                # For other exceptions, continue the loop
    finally:
        await event_service.unsubscribe_from_events(subscriber_id)


@dataclass
class _WebSocketSubscriber(Subscriber):
    websocket: WebSocket

    async def __call__(self, event: EventBase):
        try:
            dumped = event.model_dump()
            await self.websocket.send_json(dumped)
        except Exception:
            logger.exception("error_sending_event:{event}", stack_info=True)
