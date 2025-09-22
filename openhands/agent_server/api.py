from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from starlette.requests import Request

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
from openhands.sdk.logger import get_logger


logger = get_logger(__name__)


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


@api.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    # Check if this is an HTTPException that should be handled by the HTTPException
    # handler. This can happen when HTTPExceptions from middleware are unwrapped by
    # Starlette
    if isinstance(exc, HTTPException):
        return await _http_exception_handler(request, exc)

    # Check if this is an HTTPException wrapped in an ExceptionGroup (from middleware)
    # ExceptionGroup/BaseExceptionGroup has an 'exceptions' attribute
    if hasattr(exc, "exceptions"):
        exceptions = getattr(exc, "exceptions", [])
        if len(exceptions) == 1 and isinstance(exceptions[0], HTTPException):
            return await _http_exception_handler(request, exceptions[0])

    # Also check for BaseExceptionGroup (Python 3.11+)
    if exc.__class__.__name__ in ("ExceptionGroup", "BaseExceptionGroup"):
        try:
            # Try to access the exceptions attribute directly
            if hasattr(exc, "exceptions"):
                exceptions_attr = getattr(exc, "exceptions", [])
                if len(exceptions_attr) == 1:
                    inner_exc = exceptions_attr[0]
                    if isinstance(inner_exc, HTTPException):
                        return await _http_exception_handler(request, inner_exc)
        except (AttributeError, IndexError):
            pass

    # Logs full stack trace for any unhandled error that FastAPI would turn into a 500
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


@api.exception_handler(HTTPException)
async def _http_exception_handler(request: Request, exc: HTTPException):
    # Log 4xx errors at info level (expected client errors like auth failures)
    if 400 <= exc.status_code < 500:
        logger.info(
            "HTTPException %d on %s %s: %s",
            exc.status_code,
            request.method,
            request.url.path,
            exc.detail,
        )
    # Log 5xx errors at error level with full traceback (server errors)
    elif exc.status_code >= 500:
        logger.error(
            "HTTPException %d on %s %s: %s",
            exc.status_code,
            request.method,
            request.url.path,
            exc.detail,
            exc_info=True,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": "Internal Server Error\n" + str(exc.detail)},
        )

    # Return clean JSON response for all HTTP exceptions
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


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
