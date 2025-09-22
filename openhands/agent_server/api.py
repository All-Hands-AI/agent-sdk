from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

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


@asynccontextmanager
async def api_lifespan(api: FastAPI) -> AsyncIterator[None]:
    service = get_default_conversation_service()
    async with service:
        yield


def create_app(config: Config | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        config: Configuration object. If None, uses default config.

    Returns:
        Configured FastAPI application.
    """
    if config is None:
        config = get_default_config()

    app = FastAPI(
        title="OpenHands Agent Server",
        description=(
            "OpenHands Agent Server - REST/WebSocket interface for OpenHands AI Agent"
        ),
        lifespan=api_lifespan,
    )

    # Add routers
    app.include_router(conversation_event_router)
    app.include_router(conversation_router)
    app.include_router(server_details_router)
    app.include_router(tool_router)

    # Mount static files if configured and directory exists
    if (
        config.static_files_path
        and config.static_files_path.exists()
        and config.static_files_path.is_dir()
    ):
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

    # Add middleware
    app.add_middleware(LocalhostCORSMiddleware, allow_origins=config.allow_cors_origins)
    if config.session_api_key:
        app.add_middleware(
            ValidateSessionAPIKeyMiddleware, session_api_key=config.session_api_key
        )

    return app


# Create the default app instance
api = create_app()
