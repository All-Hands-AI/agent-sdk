import hmac
import os
from typing import Awaitable, Callable

from fastapi import HTTPException, Security
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


api_key_header = APIKeyHeader(name="X-Master-Key", auto_error=False)

MASTER_KEY = os.getenv("MASTER_KEY", "test")


def get_master_key(api_key: str | None = Security(api_key_header)) -> str:
    keys = _load_master_keys()
    if not keys:
        # Show as 500 to indicate misconfig, not an auth failure.
        raise HTTPException(status_code=500, detail="MASTER_KEY not configured")
    if not api_key:
        raise HTTPException(status_code=401, detail="Unauthorized: missing master key")
    if not any(hmac.compare_digest(api_key, k) for k in keys):
        raise HTTPException(status_code=401, detail="Unauthorized: invalid master key")
    return api_key


def _load_master_keys() -> list[str]:
    return [k.strip() for k in MASTER_KEY.split(",") if k.strip()]


class AuthMiddleware(BaseHTTPMiddleware):
    """Enforces X-Master-Key on all routes except allowlist."""

    def __init__(self, app, allowlist: list[str], header_name: str = "X-Master-Key"):
        super().__init__(app)
        self.allowlist = allowlist
        self.header_name = header_name
        self.keys = _load_master_keys()

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable]
    ):
        # Allow OPTIONS (CORS preflight)
        if request.method.upper() == "OPTIONS":
            return await call_next(request)

        path = request.url.path.rstrip("/") or "/"

        if path in self.allowlist:
            return await call_next(request)

        if not self.keys:
            return JSONResponse(
                status_code=500, content={"detail": "MASTER_KEY not configured"}
            )

        supplied = request.headers.get(self.header_name)
        if not supplied:
            return JSONResponse(
                status_code=401, content={"detail": "Unauthorized: missing master key"}
            )

        if not any(hmac.compare_digest(supplied, k) for k in self.keys):
            return JSONResponse(
                status_code=401, content={"detail": "Unauthorized: invalid master key"}
            )

        return await call_next(request)
