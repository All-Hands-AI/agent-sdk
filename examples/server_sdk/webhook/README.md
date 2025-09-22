# OpenHands Webhook Protocol Demo

This example demonstrates the OpenHands Webhook protocol by running two servers:

1. **Webhook Logging Server** (port 8001) - Receives and logs all webhook events
2. **OpenHands Agent Server** (port 8000) - Configured to send events to the logging server

## Quick Start

Run the complete demo with a single command:

```bash
python run_webhook_example.py
```

This will start both servers and display their URLs. Use Ctrl+C to stop both servers.

## Manual Setup

If you prefer to run the servers separately:

### 1. Start the Webhook Logging Server

```bash
python webhook_logging_server.py --port 8001
```

### 2. Start the OpenHands Agent Server

```bash
OPENHANDS_CONFIG_FILE=openhands_agent_server_config.json python -m openhands.agent_server --port 8000
```

## Configuration

The `openhands_agent_server_config.json` file configures the Agent Server to send webhook events to the logging server:

- **base_url**: `http://localhost:8001` - Where to send webhook events
- **event_buffer_size**: `5` - Number of events to batch before sending
- **num_retries**: `3` - Number of retry attempts for failed webhook calls
- **retry_delay**: `2` - Delay in seconds between retries

## Monitoring Webhook Events

Once both servers are running, you can monitor webhook activity:

- **Webhook Logging Server**: http://localhost:8001
  - View recent events: http://localhost:8001/events
  - View conversations: http://localhost:8001/conversations
  - View request logs: http://localhost:8001/logs
  - Server status: http://localhost:8001/status

- **OpenHands Agent Server**: http://localhost:8000
  - API documentation: http://localhost:8000/docs
  - Create conversations and interact with the agent to generate webhook events

## Testing the Integration

1. Create a conversation via the Agent Server API
2. Send messages to the agent
3. Watch the webhook events appear in the logging server logs and endpoints

The webhook logging server will display detailed information about each received event, including authentication status, event types, and full event data.