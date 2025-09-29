"""
WebSocket endpoints for OpenHands SDK.

These endpoints are separate from the main API routes to handle WebSocket-specific
authentication using query parameters instead of headers, since browsers cannot
send custom HTTP headers directly with WebSocket connections.
"""

import logging
from dataclasses import dataclass
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    WebSocket,
    WebSocketDisconnect,
)

from openhands.agent_server.bash_service import BashEventService
from openhands.agent_server.config import (
    get_default_config as get_default_config,
)
from openhands.agent_server.conversation_service import ConversationService
from openhands.agent_server.dependencies import (
    get_bash_event_service,
    get_conversation_service,
    websocket_session_api_key_dependency,
)
from openhands.agent_server.models import BashEventBase
from openhands.agent_server.pub_sub import Subscriber
from openhands.sdk import Message
from openhands.sdk.event.base import EventBase


# Backward-compat for tests that patch module variable
conversation_service: ConversationService | None = None


async def _resolve_conversation_service(
    svc: ConversationService = Depends(get_conversation_service),
) -> ConversationService:
    if conversation_service is not None:
        return conversation_service
    return svc


# Back-compat: allow calling events_socket directly in tests where FastAPI DI
# is not in effect. In such cases, the dependency parameter may be the Depends
# object itself; this helper normalizes it.
try:
    from fastapi.params import Depends as _DependsParam  # type: ignore
except Exception:  # pragma: no cover - fallback import structure
    _DependsParam = None  # type: ignore


sockets_router = APIRouter(prefix="/sockets", tags=["WebSockets"])
logger = logging.getLogger(__name__)


@sockets_router.websocket("/events/{conversation_id}")
async def events_socket(
    conversation_id: UUID,
    websocket: WebSocket,
    _auth: None = Depends(websocket_session_api_key_dependency),
    conv_svc: ConversationService = Depends(_resolve_conversation_service),
    session_api_key: str | None = None,
):
    """WebSocket endpoint for conversation events.

    Moved from /api/conversations/{conversation_id}/events/socket to
    /sockets/events/{conversation_id} to support browser connections with
    query parameter authentication.
    """
    # Authentication handled by dependency
    await websocket.accept()
    # Normalize dependency object when called directly (outside FastAPI DI)
    if _DependsParam is not None and isinstance(conv_svc, _DependsParam):
        conv_svc = conversation_service or ConversationService.get_instance(
            get_default_config()
        )
    event_service = await conv_svc.get_event_service(conversation_id)
    if event_service is None:
        await websocket.close(code=4004, reason="Conversation not found")
        return

    subscriber_id = await event_service.subscribe_to_events(
        _WebSocketSubscriber(websocket)
    )
    try:
        while True:
            try:
                data = await websocket.receive_json()
                message = Message.model_validate(data)
                await event_service.send_message(message)
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
    _auth: None = Depends(websocket_session_api_key_dependency),
    bash_event_service: BashEventService = Depends(get_bash_event_service),
):
    """WebSocket endpoint for bash events.

    Moved from /api/bash/bash_events/socket to /sockets/bash-events
    to support browser connections with query parameter authentication.
    """
    # Authentication handled by dependency
    await websocket.accept()
    subscriber_id = await bash_event_service.subscribe_to_events(
        _BashWebSocketSubscriber(websocket)
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
    """WebSocket subscriber for conversation events."""

    websocket: WebSocket

    async def __call__(self, event: EventBase):
        try:
            dumped = event.model_dump()
            await self.websocket.send_json(dumped)
        except Exception:
            logger.exception("error_sending_event:{event}", stack_info=True)


@dataclass
class _BashWebSocketSubscriber(Subscriber[BashEventBase]):
    """WebSocket subscriber for bash events."""

    websocket: WebSocket

    async def __call__(self, event: BashEventBase):
        try:
            dumped = event.model_dump()
            await self.websocket.send_json(dumped)
        except Exception:
            logger.exception("error_sending_bash_event:{event}", stack_info=True)
