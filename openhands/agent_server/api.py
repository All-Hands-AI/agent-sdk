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


@asynccontextmanager
async def api_lifespan(api: FastAPI) -> AsyncIterator[None]:
    service = get_default_conversation_service()
    async with service:
        yield


api = FastAPI(description="OpenHands Local Server", lifespan=api_lifespan)
config = get_default_config()


# Add routers
api.include_router(conversation_event_router)
api.include_router(conversation_router)

# Add middleware
api.add_middleware(LocalhostCORSMiddleware, allow_origins=config.allow_cors_origins)
if config.session_api_key:
    api.add_middleware(
        ValidateSessionAPIKeyMiddleware, session_api_key=config.session_api_key
    )
