from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from openhands.agent_server.config import get_default_config


_SESSION_API_KEY_HEADER = APIKeyHeader(name="X-Session-API-Key", auto_error=False)


def check_session_api_key(
    session_api_key: str | None = Depends(_SESSION_API_KEY_HEADER),
):
    """Check the session API key and throw an exception if incorrect. Having this as
    a dependency means it appears in OpenAPI Docs
    """
    config = get_default_config()
    if config.session_api_keys and session_api_key not in config.session_api_keys:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED)
