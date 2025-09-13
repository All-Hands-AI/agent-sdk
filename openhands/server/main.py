from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.requests import Request

from openhands.sdk.logger import get_logger
from openhands.server.auth import AuthMiddleware
from openhands.server.routers.conversations import (
    active_conversations,
    router as conversations_router,
)
from openhands.server.routers.server import router as server_router


logger = get_logger(__name__)


# --- Lifespan Management for graceful shutdown ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up the OpenHands Agent Server...")
    yield
    logger.info("Shutting down... cleaning up active conversations.")
    for conv_id, conversation in active_conversations.items():
        logger.info(f"Closing conversation: {conv_id}")
        conversation.close()
    active_conversations.clear()


# --- FastAPI App Initialization ---
app = FastAPI(
    title="OpenHands Agent Server",
    description="An HTTP server to create and manage AI agent "
    "conversations using the OpenHands SDK.",
    version="1.0.0",
    lifespan=lifespan,
)


# --- API Endpoints ---
# --- Centralized exception handling ---
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    # Log expected/client errors at warning level (no stack trace noise)
    logger.warning(
        "HTTPException: %s %s -> %s (%s)",
        request.method,
        request.url.path,
        exc.detail,
        exc.status_code,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Log unexpected server errors with stack trace
    logger.exception(
        "Unhandled exception during %s %s", request.method, request.url.path
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"},
    )


@app.get("/health", summary="Health Check")
async def health_check():
    return {"status": "ok"}


app.add_middleware(
    AuthMiddleware,
    allowlist=["/health", "/", "/docs", "/openapi.json"],
)

# --- Include Routers ---
app.include_router(conversations_router)
app.include_router(server_router)


# Redirect / to /docs
@app.get("/", include_in_schema=False)
async def redirect_to_docs():
    return RedirectResponse(url="/docs")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9000)
