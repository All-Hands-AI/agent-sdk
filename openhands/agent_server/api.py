from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request

from openhands.agent_server.config import (
    Config,
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


def _create_fastapi_instance() -> FastAPI:
    """Create the basic FastAPI application instance.

    Returns:
        Basic FastAPI application with title, description, and lifespan.
    """
    return FastAPI(
        title="OpenHands Agent Server",
        description=(
            "OpenHands Agent Server - REST/WebSocket interface for OpenHands AI Agent"
        ),
        lifespan=api_lifespan,
    )


def _find_http_exception(exc: BaseExceptionGroup) -> HTTPException | None:
    """Helper function to find HTTPException in ExceptionGroup.

    Args:
        exc: BaseExceptionGroup to search for HTTPException.

    Returns:
        HTTPException if found, None otherwise.
    """
    for inner_exc in exc.exceptions:
        if isinstance(inner_exc, HTTPException):
            return inner_exc
        # Recursively search nested ExceptionGroups
        if isinstance(inner_exc, BaseExceptionGroup):
            found = _find_http_exception(inner_exc)
            if found:
                return found
    return None


def _add_api_routes(app: FastAPI) -> None:
    """Add all API routes to the FastAPI application.

    Args:
        app: FastAPI application instance to add routes to.
    """
    app.include_router(conversation_event_router)
    app.include_router(conversation_router)
    app.include_router(server_details_router)
    app.include_router(tool_router)


def _setup_static_files(app: FastAPI, config: Config) -> None:
    """Set up static file serving and root redirect if configured.

    Args:
        app: FastAPI application instance.
        config: Configuration object containing static files settings.
    """
    # Only proceed if static files are configured and directory exists
    if not (
        config.static_files_path
        and config.static_files_path.exists()
        and config.static_files_path.is_dir()
    ):
        return

    # Mount static files directory
    app.mount(
        "/static",
        StaticFiles(directory=str(config.static_files_path)),
        name="static",
    )

    # Add root redirect to static files
    @app.get("/")
    async def root_redirect():
        """Redirect root endpoint to static files directory."""
        # Check if index.html exists in the static directory
        # We know static_files_path is not None here due to the outer condition
        assert config.static_files_path is not None
        index_path = config.static_files_path / "index.html"
        if index_path.exists():
            return RedirectResponse(url="/static/index.html", status_code=302)
        else:
            return RedirectResponse(url="/static/", status_code=302)


def _add_middleware(app: FastAPI, config: Config) -> None:
    """Add middleware to the FastAPI application.

    Args:
        app: FastAPI application instance.
        config: Configuration object containing middleware settings.
    """
    # Add CORS middleware
    app.add_middleware(LocalhostCORSMiddleware, allow_origins=config.allow_cors_origins)

    # Add session API key validation middleware if configured
    if config.session_api_key:
        app.add_middleware(
            ValidateSessionAPIKeyMiddleware, session_api_key=config.session_api_key
        )


def _add_exception_handlers(api: FastAPI) -> None:
    """Add exception handlers to the FastAPI application."""

    @api.exception_handler(Exception)
    async def _unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Handle unhandled exceptions."""
        # Check if this is an HTTPException that should be handled directly
        if isinstance(exc, HTTPException):
            return await _http_exception_handler(request, exc)

        # Check if this is a BaseExceptionGroup with HTTPExceptions
        if isinstance(exc, BaseExceptionGroup):
            http_exc = _find_http_exception(exc)
            if http_exc:
                return await _http_exception_handler(request, http_exc)
            # If no HTTPException found, treat as unhandled exception
            logger.exception(
                "Unhandled ExceptionGroup on %s %s", request.method, request.url.path
            )
            return JSONResponse(
                status_code=500, content={"detail": "Internal Server Error"}
            )

        # Logs full stack trace for any unhandled error that FastAPI would
        # turn into a 500
        logger.exception(
            "Unhandled exception on %s %s", request.method, request.url.path
        )
        return JSONResponse(
            status_code=500, content={"detail": "Internal Server Error"}
        )

    @api.exception_handler(HTTPException)
    async def _http_exception_handler(
        request: Request, exc: HTTPException
    ) -> JSONResponse:
        """Handle HTTPExceptions with appropriate logging."""
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
            # Don't leak internal details to clients for 5xx errors
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": "Internal Server Error"},
            )

        # Return clean JSON response for all non-5xx HTTP exceptions
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


def create_app(config: Config | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        config: Configuration object. If None, uses default config.

    Returns:
        Configured FastAPI application.
    """
    if config is None:
        config = get_default_config()
    app = _create_fastapi_instance()
    _add_api_routes(app)
    _setup_static_files(app, config)
    _add_middleware(app, config)
    _add_exception_handlers(app)

    return app


# Create the default app instance
api = create_app()
