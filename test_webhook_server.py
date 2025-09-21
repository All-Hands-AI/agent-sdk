#!/usr/bin/env python3
"""
Test script for the OpenHands webhook test server.

This script sends sample webhook requests to test both endpoints:
- /events (batched events)
- /conversations (conversation lifecycle events)
"""

import asyncio
import json
from datetime import datetime
from uuid import uuid4

import httpx


async def test_webhook_server(base_url: str = "http://localhost:12000"):
    """Test the webhook server with sample data."""
    print(f"Testing webhook server at {base_url}")

    async with httpx.AsyncClient() as client:
        # Test server status
        print("\n1. Testing server status...")
        try:
            response = await client.get(f"{base_url}/")
            print(f"Server response: {response.status_code}")
            print(json.dumps(response.json(), indent=2))
        except Exception as e:
            print(f"Error connecting to server: {e}")
            return

        # Test events endpoint with sample events
        print("\n2. Testing /events endpoint...")
        sample_events = [
            {
                "type": "MessageEvent",
                "source": "user",
                "timestamp": datetime.utcnow().isoformat(),
                "llm_message": {
                    "role": "user",
                    "content": [{"type": "text", "text": "Hello, world!"}],
                },
            },
            {
                "type": "MessageEvent",
                "source": "assistant",
                "timestamp": datetime.utcnow().isoformat(),
                "llm_message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "Hello! How can I help you?"}],
                },
            },
            {
                "type": "ActionEvent",
                "source": "agent",
                "timestamp": datetime.utcnow().isoformat(),
                "action": {"type": "bash", "command": "echo 'test command'"},
            },
        ]

        headers = {
            "Content-Type": "application/json",
            "X-Session-API-Key": "test-session-key",
            "Authorization": "Bearer test-token",
        }

        try:
            response = await client.post(
                f"{base_url}/events", json=sample_events, headers=headers
            )
            print(f"Events response: {response.status_code}")
            print(json.dumps(response.json(), indent=2))
        except Exception as e:
            print(f"Error sending events: {e}")

        # Test conversations endpoint with sample conversation
        print("\n3. Testing /conversations endpoint...")
        conversation_id = str(uuid4())
        sample_conversation = {
            "id": conversation_id,
            "status": "RUNNING",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "llm": {
                "model": "litellm_proxy/anthropic/claude-sonnet-4-20250514",
                "base_url": "https://llm-proxy.staging.all-hands.dev",
                "api_key": "***",
            },
            "confirmation_mode": False,
            "max_iterations": 500,
        }

        try:
            response = await client.post(
                f"{base_url}/conversations", json=sample_conversation, headers=headers
            )
            print(f"Conversation response: {response.status_code}")
            print(json.dumps(response.json(), indent=2))
        except Exception as e:
            print(f"Error sending conversation: {e}")

        # Test conversation status change
        print("\n4. Testing conversation status change...")
        sample_conversation["status"] = "PAUSED"
        sample_conversation["updated_at"] = datetime.utcnow().isoformat()

        try:
            response = await client.post(
                f"{base_url}/conversations", json=sample_conversation, headers=headers
            )
            print(f"Conversation status change response: {response.status_code}")
            print(json.dumps(response.json(), indent=2))
        except Exception as e:
            print(f"Error sending conversation status change: {e}")

        # Get server status after tests
        print("\n5. Getting server status after tests...")
        try:
            response = await client.get(f"{base_url}/status")
            print(f"Final status: {response.status_code}")
            print(json.dumps(response.json(), indent=2))
        except Exception as e:
            print(f"Error getting status: {e}")

        # Get received data
        print("\n6. Getting received events...")
        try:
            response = await client.get(f"{base_url}/events")
            print(f"Received events: {response.status_code}")
            print(json.dumps(response.json(), indent=2))
        except Exception as e:
            print(f"Error getting events: {e}")

        print("\n7. Getting received conversations...")
        try:
            response = await client.get(f"{base_url}/conversations")
            print(f"Received conversations: {response.status_code}")
            print(json.dumps(response.json(), indent=2))
        except Exception as e:
            print(f"Error getting conversations: {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test the webhook server")
    parser.add_argument(
        "--url",
        default="http://localhost:12000",
        help="Base URL of the webhook server (default: http://localhost:12000)",
    )

    args = parser.parse_args()

    asyncio.run(test_webhook_server(args.url))
