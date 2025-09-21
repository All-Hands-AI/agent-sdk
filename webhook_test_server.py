#!/usr/bin/env python3
"""
FastAPI test server for testing the expanded OpenHands webhook protocol.

This server implements the webhook endpoints that the OpenHands agent server
sends data to:
- /events: Receives batched events from WebhookSubscriber
- /conversations: Receives conversation lifecycle events from
  ConversationWebhookSubscriber

The server provides comprehensive logging and monitoring to help test and debug
webhook integrations.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, Header, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("webhook_test_server.log"),
    ],
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="OpenHands Webhook Test Server",
    description="Test server for the expanded OpenHands webhook protocol",
    version="1.0.0",
)

# Add CORS middleware to allow requests from any origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for received data (for testing purposes)
received_events: List[Dict[str, Any]] = []
received_conversations: List[Dict[str, Any]] = []
request_logs: List[Dict[str, Any]] = []

# Configuration
EXPECTED_SESSION_API_KEY = "test-session-key"  # Set this to test authentication


class EventBatch(BaseModel):
    """Model for batched events received from WebhookSubscriber."""

    events: List[Dict[str, Any]] = Field(
        default_factory=list, description="List of events in the batch"
    )


class ConversationInfo(BaseModel):
    """Model for conversation lifecycle events."""

    id: str = Field(description="Conversation UUID")
    status: str = Field(description="Current conversation status")
    created_at: str = Field(description="ISO timestamp when conversation was created")
    updated_at: str = Field(
        description="ISO timestamp when conversation was last updated"
    )
    llm: Optional[Dict[str, Any]] = Field(default=None, description="LLM configuration")
    confirmation_mode: Optional[bool] = Field(
        default=False, description="Whether confirmation mode is enabled"
    )
    max_iterations: Optional[int] = Field(
        default=500, description="Maximum iterations for the conversation"
    )


def log_request(
    endpoint: str,
    method: str,
    headers: Dict[str, str],
    body: Any,
    authenticated: bool = False,
):
    """Log incoming webhook requests for debugging."""
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "endpoint": endpoint,
        "method": method,
        "headers": dict(headers),
        "body": body,
        "authenticated": authenticated,
    }
    request_logs.append(log_entry)
    logger.info(f"Request to {endpoint}: {json.dumps(log_entry, indent=2)}")


@app.get("/")
async def root():
    """Root endpoint with server information."""
    return {
        "message": "OpenHands Webhook Test Server",
        "version": "1.0.0",
        "endpoints": {
            "/events": "POST - Receive batched events from WebhookSubscriber",
            "/conversations": "POST - Receive conversation lifecycle events",
            "/status": "GET - Server status and statistics",
            "/logs": "GET - View request logs",
            "/clear": "POST - Clear stored data",
        },
    }


@app.post("/events")
async def receive_events(
    request: Request,
    events: List[Dict[str, Any]],
    x_session_api_key: Optional[str] = Header(None, alias="X-Session-API-Key"),
    authorization: Optional[str] = Header(None),
    content_type: Optional[str] = Header(None, alias="Content-Type"),
):
    """
    Receive batched events from WebhookSubscriber.

    This endpoint receives events that are batched according to the
    event_buffer_size configuration in WebhookSpec.
    """
    # Check authentication if expected
    authenticated = True
    if EXPECTED_SESSION_API_KEY and x_session_api_key != EXPECTED_SESSION_API_KEY:
        authenticated = False
        logger.warning(
            f"Authentication failed. Expected: {EXPECTED_SESSION_API_KEY}, "
            f"Got: {x_session_api_key}"
        )

    # Log the request
    headers = dict(request.headers)
    log_request("/events", "POST", headers, events, authenticated)

    # Store the events
    event_batch = {
        "timestamp": datetime.utcnow().isoformat(),
        "batch_size": len(events),
        "events": events,
        "headers": headers,
        "authenticated": authenticated,
    }
    received_events.append(event_batch)

    logger.info(f"Received batch of {len(events)} events")
    for i, event in enumerate(events):
        logger.info(f"Event {i + 1}: {json.dumps(event, indent=2)}")

    return {
        "status": "success",
        "message": f"Received {len(events)} events",
        "batch_id": len(received_events),
        "authenticated": authenticated,
    }


@app.post("/conversations")
async def receive_conversation_info(
    request: Request,
    conversation: Dict[str, Any],
    x_session_api_key: Optional[str] = Header(None, alias="X-Session-API-Key"),
    authorization: Optional[str] = Header(None),
    content_type: Optional[str] = Header(None, alias="Content-Type"),
):
    """
    Receive conversation lifecycle events from ConversationWebhookSubscriber.

    This endpoint receives individual conversation events (not batched)
    for conversation lifecycle events like start, pause, resume, delete.
    """
    # Check authentication if expected
    authenticated = True
    if EXPECTED_SESSION_API_KEY and x_session_api_key != EXPECTED_SESSION_API_KEY:
        authenticated = False
        logger.warning(
            f"Authentication failed. Expected: {EXPECTED_SESSION_API_KEY}, "
            f"Got: {x_session_api_key}"
        )

    # Log the request
    headers = dict(request.headers)
    log_request("/conversations", "POST", headers, conversation, authenticated)

    # Store the conversation info
    conversation_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "conversation": conversation,
        "headers": headers,
        "authenticated": authenticated,
    }
    received_conversations.append(conversation_entry)

    conversation_id = conversation.get("id", "unknown")
    conversation_status = conversation.get("status", "unknown")

    logger.info(
        f"Received conversation event - ID: {conversation_id}, "
        f"Status: {conversation_status}"
    )
    logger.info(f"Conversation data: {json.dumps(conversation, indent=2)}")

    return {
        "status": "success",
        "message": f"Received conversation event for {conversation_id}",
        "conversation_id": conversation_id,
        "conversation_status": conversation_status,
        "authenticated": authenticated,
    }


@app.get("/status")
async def get_status():
    """Get server status and statistics."""
    return {
        "server": "OpenHands Webhook Test Server",
        "status": "running",
        "statistics": {
            "total_event_batches": len(received_events),
            "total_events": sum(batch["batch_size"] for batch in received_events),
            "total_conversations": len(received_conversations),
            "total_requests": len(request_logs),
        },
        "last_event_batch": (
            received_events[-1]["timestamp"] if received_events else None
        ),
        "last_conversation": (
            received_conversations[-1]["timestamp"] if received_conversations else None
        ),
    }


@app.get("/logs")
async def get_logs(limit: int = 50):
    """Get recent request logs."""
    return {
        "logs": request_logs[-limit:],
        "total_logs": len(request_logs),
        "showing": min(limit, len(request_logs)),
    }


@app.get("/events")
async def get_received_events(limit: int = 10):
    """Get recently received event batches."""
    return {
        "event_batches": received_events[-limit:],
        "total_batches": len(received_events),
        "showing": min(limit, len(received_events)),
    }


@app.get("/conversations")
async def get_received_conversations(limit: int = 10):
    """Get recently received conversation events."""
    return {
        "conversations": received_conversations[-limit:],
        "total_conversations": len(received_conversations),
        "showing": min(limit, len(received_conversations)),
    }


@app.post("/clear")
async def clear_data():
    """Clear all stored data."""
    global received_events, received_conversations, request_logs

    events_count = len(received_events)
    conversations_count = len(received_conversations)
    logs_count = len(request_logs)

    received_events.clear()
    received_conversations.clear()
    request_logs.clear()

    logger.info("Cleared all stored data")

    return {
        "status": "success",
        "message": "All data cleared",
        "cleared": {
            "event_batches": events_count,
            "conversations": conversations_count,
            "request_logs": logs_count,
        },
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for debugging."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "message": str(exc),
            "endpoint": str(request.url),
        },
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="OpenHands Webhook Test Server")
    parser.add_argument(
        "--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=12000, help="Port to bind to (default: 12000)"
    )
    parser.add_argument(
        "--session-key",
        default="test-session-key",
        help="Expected session API key for authentication",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Log level (default: INFO)",
    )

    args = parser.parse_args()

    # Update global configuration
    EXPECTED_SESSION_API_KEY = args.session_key

    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    logger.info(f"Starting OpenHands Webhook Test Server on {args.host}:{args.port}")
    logger.info(f"Expected session API key: {args.session_key}")
    logger.info(f"Log level: {args.log_level}")

    # Run the server
    uvicorn.run(
        "webhook_test_server:app",
        host=args.host,
        port=args.port,
        log_level=args.log_level.lower(),
        reload=False,
    )
