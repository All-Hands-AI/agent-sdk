from typing import Annotated

from fastapi import Depends, HTTPException, Query, Request, WebSocket, status
from fastapi.security import APIKeyHeader

from openhands.agent_server.config import Config, get_default_config


_SESSION_API_KEY_HEADER = APIKeyHeader(name="X-Session-API-Key", auto_error=False)


def create_session_api_key_dependency(config: Config):
    """Create a session API key dependency with the given config."""

    def check_session_api_key(
        session_api_key: str | None = Depends(_SESSION_API_KEY_HEADER),
    ):
        """Check the session API key and throw an exception if incorrect. Having this as
        a dependency means it appears in OpenAPI Docs
        """
        if config.session_api_keys and session_api_key not in config.session_api_keys:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED)

    return check_session_api_key


def check_session_api_key(
    session_api_key: str | None = Depends(_SESSION_API_KEY_HEADER),
):
    """Check the session API key and throw an exception if incorrect. Having this as
    a dependency means it appears in OpenAPI Docs.

    This uses the default config - for testing or custom configs, use
    create_session_api_key_dependency() instead.
    """
    config = get_default_config()
    if config.session_api_keys and session_api_key not in config.session_api_keys:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED)


def create_websocket_session_api_key_dependency(config: Config):
    """Create a WebSocket session API key dependency that uses query parameters.

    WebSocket connections cannot send custom headers using the standard WebSocket API
    in browsers, so we use query parameters instead.
    """

    def check_websocket_session_api_key(
        session_api_key: Annotated[
            str | None,
            Query(description="Session API key for WebSocket authentication"),
        ] = None,
    ):
        """Check the session API key from query parameters for WebSocket connections."""
        if config.session_api_keys and session_api_key not in config.session_api_keys:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED)

    return check_websocket_session_api_key


def check_websocket_session_api_key(
    session_api_key: Annotated[
        str | None, Query(description="Session API key for WebSocket authentication")
    ] = None,
):
    """Check the session API key from query parameters for WebSocket connections.

    This uses the default config - for testing or custom configs, use
    create_websocket_session_api_key_dependency() instead.
    """
    config = get_default_config()
    if config.session_api_keys and session_api_key not in config.session_api_keys:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED)


def create_conditional_session_api_key_dependency(config: Config):
    """Create a conditional session API key dependency for both HTTP and WebSocket.

    For HTTP requests, it uses header-based authentication.
    For WebSocket requests, it skips authentication (WebSocket endpoints handle it
    internally).
    """

    async def conditional_check_session_api_key(request: Request):
        """Check session API key conditionally based on request type."""
        # Skip authentication for WebSocket connections
        # WebSocket endpoints handle authentication internally via query parameters
        if request.scope.get("type") == "websocket":
            return None

        # Apply header-based authentication for HTTP requests
        # Extract the header manually for HTTP requests
        session_api_key = request.headers.get("X-Session-API-Key")
        if config.session_api_keys and session_api_key not in config.session_api_keys:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED)

    return conditional_check_session_api_key


def check_session_api_key_from_app(request: Request):
    """Check session API key using config from app state."""
    # Get the config from the app's state
    config = request.app.state.config

    # Extract the header manually
    session_api_key = request.headers.get("X-Session-API-Key")

    if config.session_api_keys and session_api_key not in config.session_api_keys:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED)


async def check_websocket_session_api_key_from_app(
    websocket: WebSocket,
    session_api_key: Annotated[str | None, Query()] = None,
):
    """Check WebSocket session API key using config from app state."""
    # Get the config from the app's state
    config = websocket.app.state.config

    if config.session_api_keys and session_api_key not in config.session_api_keys:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED)
