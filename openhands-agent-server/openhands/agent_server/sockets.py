"""
WebSocket endpoints for OpenHands SDK.

These endpoints are separate from the main API routes to handle WebSocket-specific
authentication using query parameters instead of headers, since browsers cannot
send custom HTTP headers directly with WebSocket connections.
"""

import logging
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Query,
    WebSocket,
    WebSocketDisconnect,
)

from openhands.agent_server.bash_service import get_default_bash_event_service
from openhands.agent_server.config import get_default_config
from openhands.agent_server.conversation_service import (
    get_default_conversation_service,
)
from openhands.agent_server.models import BashEventBase
from openhands.agent_server.pub_sub import Subscriber
from openhands.sdk import Event, Message


sockets_router = APIRouter(prefix="/sockets", tags=["WebSockets"])
conversation_service = get_default_conversation_service()
bash_event_service = get_default_bash_event_service()
logger = logging.getLogger(__name__)


@sockets_router.websocket("/events/{conversation_id}")
async def events_socket(
    conversation_id: UUID,
    websocket: WebSocket,
    session_api_key: Annotated[str | None, Query(alias="session_api_key")] = None,
    resend_all: Annotated[bool, Query()] = False,
):
    """WebSocket endpoint for conversation events."""
    # Perform authentication check before accepting the WebSocket connection
    config = get_default_config()
    if config.session_api_keys and session_api_key not in config.session_api_keys:
        # Close the WebSocket connection with an authentication error code
        await websocket.close(code=4001, reason="Authentication failed")
        return

    await websocket.accept()
    event_service = await conversation_service.get_event_service(conversation_id)
    if event_service is None:
        await websocket.close(code=4004, reason="Conversation not found")
        return

    subscriber_id = await event_service.subscribe_to_events(
        _WebSocketSubscriber(websocket)
    )

    try:
        # Resend all existing events if requested
        if resend_all:
            page_id = None
            while True:
                page = await event_service.search_events(page_id=page_id)
                for event in page.items:
                    await _send_event(event, websocket)
                page_id = page.next_page_id
                if not page_id:
                    break

        # Listen for messages over the socket
        while True:
            try:
                data = await websocket.receive_json()
                message = Message.model_validate(data)
                await event_service.send_message(message, True)
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


@sockets_router.websocket("/bash-events")
async def bash_events_socket(
    websocket: WebSocket,
    session_api_key: Annotated[str | None, Query(alias="session_api_key")] = None,
    resend_all: Annotated[bool, Query()] = False,
):
    """WebSocket endpoint for bash events."""
    # Perform authentication check before accepting the WebSocket connection
    config = get_default_config()
    if config.session_api_keys and session_api_key not in config.session_api_keys:
        # Close the WebSocket connection with an authentication error code
        await websocket.close(code=4001, reason="Authentication failed")
        return

    await websocket.accept()
    subscriber_id = await bash_event_service.subscribe_to_events(
        _BashWebSocketSubscriber(websocket)
    )
    try:
        # Resend all existing events if requested
        if resend_all:
            page_id = None
            while True:
                page = await bash_event_service.search_bash_events(page_id=page_id)
                for event in page.items:
                    await _send_bash_event(event, websocket)
                page_id = page.next_page_id
                if not page_id:
                    break

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


async def _send_event(event: Event, websocket: WebSocket):
    try:
        dumped = event.model_dump()
        await websocket.send_json(dumped)
    except Exception:
        logger.exception("error_sending_event:{event}", stack_info=True)


@dataclass
class _WebSocketSubscriber(Subscriber):
    """WebSocket subscriber for conversation events."""

    websocket: WebSocket

    async def __call__(self, event: Event):
        await _send_event(event, self.websocket)


async def _send_bash_event(event: BashEventBase, websocket: WebSocket):
    try:
        dumped = event.model_dump()
        await websocket.send_json(dumped)
    except Exception:
        logger.exception("error_sending_event:{event}", stack_info=True)


@dataclass
class _BashWebSocketSubscriber(Subscriber[BashEventBase]):
    """WebSocket subscriber for bash events."""

    websocket: WebSocket

    async def __call__(self, event: BashEventBase):
        await _send_bash_event(event, self.websocket)
