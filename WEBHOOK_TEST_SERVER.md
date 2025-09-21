# OpenHands Webhook Test Server

This directory contains a FastAPI-based test server for testing the expanded OpenHands webhook protocol introduced in the `expand-webhook-protocol` branch.

## Overview

The webhook protocol has been expanded to support conversation lifecycle events:

- **Events Endpoint** (`/events`): Receives batched events from `WebhookSubscriber`
- **Conversations Endpoint** (`/conversations`): Receives conversation lifecycle events from `ConversationWebhookSubscriber`

## Protocol Changes

### WebhookSpec Changes
- Changed `webhook_url` to `base_url` for cleaner URL construction
- Events are sent to `{base_url}/events` (batched)
- Conversation info is sent to `{base_url}/conversations` (unbatched)

### New Features
- `ConversationWebhookSubscriber` for conversation lifecycle events
- Webhook notifications for start/pause/resume/delete conversation events
- Improved retry logic and error handling
- Session API key authentication support

## Files

- `webhook_test_server.py` - Main FastAPI test server
- `test_webhook_server.py` - Test script to verify server functionality
- `WEBHOOK_TEST_SERVER.md` - This documentation file

## Installation

The test server requires FastAPI and uvicorn. Install dependencies:

```bash
# Install FastAPI and uvicorn
pip install fastapi uvicorn httpx

# Or if using the project's uv environment:
uv add fastapi uvicorn httpx
```

## Usage

### Starting the Test Server

```bash
# Basic usage (runs on localhost:12000)
python webhook_test_server.py

# Custom host and port
python webhook_test_server.py --host 0.0.0.0 --port 8080

# With custom session API key
python webhook_test_server.py --session-key "my-secret-key"

# With debug logging
python webhook_test_server.py --log-level DEBUG
```

### Command Line Options

- `--host`: Host to bind to (default: 0.0.0.0)
- `--port`: Port to bind to (default: 12000)
- `--session-key`: Expected session API key for authentication (default: test-session-key)
- `--log-level`: Log level - DEBUG, INFO, WARNING, ERROR (default: INFO)

### Testing the Server

Run the test script to verify functionality:

```bash
# Test against default server (localhost:12000)
python test_webhook_server.py

# Test against custom URL
python test_webhook_server.py --url http://localhost:8080
```

## API Endpoints

### POST /events
Receives batched events from WebhookSubscriber.

**Request Body**: Array of event objects
**Headers**:
- `Content-Type: application/json`
- `X-Session-API-Key: <session-key>` (optional)
- `Authorization: Bearer <token>` (optional)

**Example**:
```json
[
  {
    "type": "MessageEvent",
    "source": "user",
    "timestamp": "2025-09-21T10:30:00Z",
    "llm_message": {
      "role": "user",
      "content": [{"type": "text", "text": "Hello!"}]
    }
  }
]
```

### POST /conversations
Receives conversation lifecycle events from ConversationWebhookSubscriber.

**Request Body**: Conversation info object
**Headers**: Same as /events

**Example**:
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "RUNNING",
  "created_at": "2025-09-21T10:30:00Z",
  "updated_at": "2025-09-21T10:30:00Z",
  "llm": {
    "model": "claude-sonnet-4",
    "base_url": "https://api.anthropic.com"
  },
  "confirmation_mode": false,
  "max_iterations": 500
}
```

### GET /status
Returns server status and statistics.

### GET /events
Returns recently received event batches.

### GET /conversations  
Returns recently received conversation events.

### GET /logs
Returns recent request logs for debugging.

### POST /clear
Clears all stored data.

## Configuration for OpenHands Agent Server

To configure the OpenHands agent server to use this test server, create a webhook configuration:

```json
{
  "webhooks": [
    {
      "base_url": "http://localhost:12000",
      "event_buffer_size": 10,
      "method": "POST",
      "headers": {
        "Content-Type": "application/json",
        "Authorization": "Bearer your-token"
      },
      "num_retries": 3,
      "retry_delay": 5
    }
  ]
}
```

## Logging

The server logs all requests to both console and `webhook_test_server.log` file. Logs include:

- Incoming webhook requests with full headers and body
- Authentication status
- Event and conversation processing
- Error details for debugging

## Testing with Real OpenHands Agent Server

1. Start the webhook test server:
   ```bash
   python webhook_test_server.py --port 12000
   ```

2. Configure your OpenHands agent server with webhook pointing to the test server

3. Start conversations and observe the webhook calls in the test server logs

4. Use the `/status`, `/events`, and `/conversations` endpoints to inspect received data

## Development

The test server is designed to be easily extensible. You can:

- Add custom validation logic for webhook payloads
- Implement custom response behaviors for testing error scenarios
- Add database persistence instead of in-memory storage
- Integrate with monitoring systems

## Troubleshooting

### Common Issues

1. **Connection refused**: Make sure the server is running and accessible
2. **Authentication failures**: Check the session API key configuration
3. **JSON parsing errors**: Verify the request content-type and payload format

### Debug Mode

Run with debug logging to see detailed request information:

```bash
python webhook_test_server.py --log-level DEBUG
```

This will show all HTTP request details, headers, and processing steps.