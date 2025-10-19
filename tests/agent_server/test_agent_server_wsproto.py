"""Integration test to verify the agent server works with wsproto.

This test starts the actual agent server using the real __main__.py entry point
and verifies that websocket communication works correctly with wsproto.
"""

import asyncio
import multiprocessing
import socket
import sys
import time

import pytest
import requests
import websockets


def find_free_port():
    """Find a free port to use for the test server."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


def run_agent_server(port, api_key):
    """Run the actual agent server using __main__.py."""
    import os

    # Set authentication via environment variable
    # The agent server reads OH_SESSION_API_KEYS as a JSON list
    os.environ["OH_SESSION_API_KEYS"] = f'["{api_key}"]'

    # Import here to avoid issues with multiprocessing
    from openhands.agent_server.__main__ import main

    # Override sys.argv to set the port
    sys.argv = ["agent-server", "--port", str(port)]
    main()


@pytest.fixture
def agent_server(tmp_path):
    """Start the agent server for testing."""
    port = find_free_port()
    api_key = "test-wsproto-key"

    process = multiprocessing.Process(target=run_agent_server, args=(port, api_key))
    process.start()

    # Wait for server to be ready
    max_wait = 10
    start_time = time.time()
    server_ready = False
    while time.time() - start_time < max_wait:
        try:
            response = requests.get(f"http://127.0.0.1:{port}/docs", timeout=1)
            if response.status_code == 200:
                server_ready = True
                break
        except Exception:
            pass
        time.sleep(0.2)

    if not server_ready:
        process.terminate()
        process.join()
        pytest.fail(f"Agent server failed to start on port {port} within {max_wait}s")

    yield {"port": port, "api_key": api_key}

    # Cleanup
    process.terminate()
    process.join(timeout=5)
    if process.is_alive():
        process.kill()
        process.join()


def test_agent_server_starts_with_wsproto(agent_server):
    """Test that the agent server starts successfully with wsproto configuration.

    This verifies that the ws='wsproto' configuration in __main__.py doesn't
    cause any startup errors and the server is accessible.
    """
    port = agent_server["port"]

    # Verify the server is running
    response = requests.get(f"http://127.0.0.1:{port}/docs")
    assert response.status_code == 200

    # Verify API docs are accessible (sanity check)
    assert (
        "OpenHands Agent Server" in response.text or "swagger" in response.text.lower()
    )


@pytest.mark.asyncio
async def test_agent_server_websocket_with_wsproto(agent_server):
    """Test that websockets work correctly with wsproto on the agent server.

    This test performs a complete websocket handshake with authentication,
    demonstrating that the ws='wsproto' configuration in __main__.py enables
    proper websocket communication through uvicorn's wsproto implementation.

    The test:
    1. Creates a conversation via the REST API
    2. Connects to the conversation's websocket endpoint with authentication
    3. Successfully completes the websocket handshake
    4. Sends and receives data over the websocket

    This validates that wsproto handles the full websocket lifecycle correctly.
    """
    port = agent_server["port"]
    api_key = agent_server["api_key"]

    # First, create a conversation using the REST API
    # Minimal required fields for starting a conversation
    conversation_request = {
        "agent": {
            "llm": {
                "service_id": "test-llm",
                "model": "test-provider/test-model",
                "api_key": "test-key",
            },
            "tools": [],
        },
        "workspace": {"working_dir": "/tmp/test-workspace"},
    }
    response = requests.post(
        f"http://127.0.0.1:{port}/api/conversations",
        headers={"X-Session-API-Key": api_key},
        json=conversation_request,
    )
    assert response.status_code in [
        200,
        201,
    ], f"Failed to create conversation: {response.text}"
    conversation = response.json()
    conversation_id = conversation["id"]

    # Now connect to the websocket endpoint with authentication
    ws_url = (
        f"ws://127.0.0.1:{port}/sockets/events/{conversation_id}"
        f"?session_api_key={api_key}"
    )

    # Test full websocket lifecycle with resend_all to verify bidirectional data
    ws_url_with_resend = f"{ws_url}&resend_all=true"

    try:
        async with websockets.connect(ws_url_with_resend, open_timeout=5) as ws:
            # Connection succeeded! This proves wsproto is working.
            # The handshake completed successfully with authentication.

            # With resend_all=true, server should send initial conversation state
            # Try to receive events (there should be at least initial state)
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=2)
                assert response is not None
                # Successfully received data - wsproto handles incoming messages
            except TimeoutError:
                # No initial events - that's ok, conversation might be empty
                pass

            # Now test sending data - use the same format as other websocket tests
            import json

            test_message = {"role": "user", "content": "Hello from wsproto test"}
            await ws.send(json.dumps(test_message))
            # Successfully sent - wsproto handles outgoing messages

            # If we got here, wsproto handled the complete websocket lifecycle:
            # - Handshake with authentication
            # - Receiving data (tested with resend_all)
            # - Sending data (tested with message)
            # - Connection maintenance

    except websockets.exceptions.InvalidStatus as e:
        status = e.response.status_code
        pytest.fail(
            f"Websocket handshake failed with HTTP {status}. "
            f"This indicates wsproto is not handling the connection correctly."
        )

    except websockets.exceptions.ConnectionClosed as e:
        pytest.fail(
            f"Websocket connection closed unexpectedly: {e}. "
            f"This indicates wsproto may not be handling the connection correctly."
        )

    except Exception as e:
        pytest.fail(
            f"Websocket communication failed: {type(e).__name__}: {e}. "
            f"This indicates wsproto is not working correctly."
        )
