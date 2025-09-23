from urllib.parse import urlparse

from fastapi import Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse
from starlette.types import ASGIApp


class LocalhostCORSMiddleware(CORSMiddleware):
    """Custom CORS middleware that allows any request from localhost/127.0.0.1 domains,
    while using standard CORS rules for other origins.
    """

    def __init__(self, app: ASGIApp, allow_origins: list[str]) -> None:
        super().__init__(
            app,
            allow_origins=allow_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def is_allowed_origin(self, origin: str) -> bool:
        if origin and not self.allow_origins and not self.allow_origin_regex:
            parsed = urlparse(origin)
            hostname = parsed.hostname or ""

            # Allow any localhost/127.0.0.1 origin regardless of port
            if hostname in ["localhost", "127.0.0.1"]:
                return True

        # For missing origin or other origins, use the parent class's logic
        result: bool = super().is_allowed_origin(origin)
        return result


class ValidateSessionAPIKeyMiddleware(BaseHTTPMiddleware):
    """Middleware to validate session API key for all requests

    Inside a sandbox, conversations are run locally, and there is a Session API key
    for the sandbox that needs provided.

    Note: the Session API key is occasionally sent to the client.
    """

    def __init__(self, app: ASGIApp, session_api_keys: list[str]) -> None:
        super().__init__(app)
        self.session_api_keys = session_api_keys

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Skip authentication for health check and server info endpoints
        if request.url.path not in ["/alive", "/health", "/server_info"]:
            session_api_key = request.headers.get("X-Session-API-Key")
            if session_api_key not in self.session_api_keys:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Unauthorized"},
                )
        response = await call_next(request)
        return response
