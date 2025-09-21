from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from openhands.agent_server.config import (
    get_default_config,
)
from openhands.agent_server.conversation_router import (
    router as conversation_router,
)
from openhands.agent_server.conversation_service import (
    get_default_conversation_service,
)
from openhands.agent_server.event_router import (
    router as conversation_event_router,
)
from openhands.agent_server.middleware import (
    LocalhostCORSMiddleware,
    ValidateSessionAPIKeyMiddleware,
)
from openhands.agent_server.server_details_router import router as server_details_router
from openhands.agent_server.tool_router import router as tool_router


@asynccontextmanager
async def api_lifespan(api: FastAPI) -> AsyncIterator[None]:
    service = get_default_conversation_service()
    async with service:
        yield


api = FastAPI(
    title="OpenHands Agent Server",
    description=(
        "OpenHands Agent Server - REST/WebSocket interface for OpenHands AI Agent"
    ),
    lifespan=api_lifespan,
)
config = get_default_config()


# Add routers
api.include_router(conversation_event_router)
api.include_router(conversation_router)
api.include_router(server_details_router)
api.include_router(tool_router)

# Add middleware
api.add_middleware(LocalhostCORSMiddleware, allow_origins=config.allow_cors_origins)
if config.session_api_key:
    api.add_middleware(
        ValidateSessionAPIKeyMiddleware, session_api_key=config.session_api_key
    )
