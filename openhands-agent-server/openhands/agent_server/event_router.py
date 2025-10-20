"""
Local Event router for OpenHands SDK.
"""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
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
from openhands.sdk import Message
from openhands.sdk.event import Event


event_router = APIRouter(
    prefix="/conversations/{conversation_id}/events", tags=["Events"]
)
conversation_service = get_default_conversation_service()
logger = logging.getLogger(__name__)

# Read methods


@event_router.get("/search", responses={404: {"description": "Conversation not found"}})
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


@event_router.get("/count", responses={404: {"description": "Conversation not found"}})
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


@event_router.get("/{event_id}", responses={404: {"description": "Item not found"}})
async def get_conversation_event(conversation_id: UUID, event_id: str) -> Event:
    """Get a local event given an id"""
    event_service = await conversation_service.get_event_service(conversation_id)
    if event_service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    event = await event_service.get_event(event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return event


@event_router.get("")
async def batch_get_conversation_events(
    conversation_id: UUID, event_ids: list[str]
) -> list[Event | None]:
    """Get a batch of local events given their ids, returning null for any
    missing item."""
    event_service = await conversation_service.get_event_service(conversation_id)
    if event_service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    events = await event_service.batch_get_events(event_ids)
    return events


@event_router.post("")
async def send_message(conversation_id: UUID, request: SendMessageRequest) -> Success:
    """Send a message to a conversation"""
    event_service = await conversation_service.get_event_service(conversation_id)
    if event_service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    message = Message(role=request.role, content=request.content)
    await event_service.send_message(message, request.run)
    return Success()


@event_router.post(
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
