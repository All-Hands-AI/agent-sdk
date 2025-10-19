"""Integration test to verify the agent server works with wsproto.

This test starts the actual agent server using the real __main__.py entry point
and verifies that websocket communication works correctly with wsproto.
"""

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


def run_agent_server(port, config_file):
    """Run the actual agent server using __main__.py."""
    import os

    # Set config file environment variable
    os.environ["OPENHANDS_AGENT_SERVER_CONFIG_PATH"] = config_file

    # Import here to avoid issues with multiprocessing
    from openhands.agent_server.__main__ import main

    # Override sys.argv to set the port
    sys.argv = ["agent-server", "--port", str(port)]
    main()


@pytest.fixture
def agent_server(tmp_path):
    """Start the agent server for testing."""
    import json

    port = find_free_port()

    # Create a minimal config file with no authentication for testing
    config_file = tmp_path / "test_config.json"
    config_file.write_text(json.dumps({"session_api_keys": []}))

    process = multiprocessing.Process(
        target=run_agent_server, args=(port, str(config_file))
    )
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

    yield port

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
    port = agent_server

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

    This test connects to an actual websocket endpoint on the agent server
    to verify that the ws='wsproto' configuration in __main__.py enables
    proper websocket communication through uvicorn's wsproto implementation.

    The key validation is that uvicorn uses wsproto to handle the websocket
    handshake - this is confirmed by getting a proper HTTP status response
    (like 403) rather than connection errors. The status code itself doesn't
    matter; what matters is that wsproto successfully negotiated the websocket
    protocol and returned a proper HTTP response.
    """
    port = agent_server

    # Connect to the bash-events websocket endpoint
    ws_url = f"ws://127.0.0.1:{port}/sockets/bash-events"

    try:
        # Try to establish a websocket connection
        async with websockets.connect(ws_url, open_timeout=5):
            # If we get here, the websocket connection succeeded!
            # This proves that wsproto is working correctly.
            pass

    except websockets.exceptions.InvalidStatus as e:
        # Server responded with an HTTP status during websocket handshake.
        # This is GOOD - it proves wsproto handled the websocket protocol correctly.
        # Common statuses:
        # - 403: Authentication required (expected for agent server)
        # - 401: Unauthorized
        # - 404: Endpoint not found
        status = e.response.status_code

        if status in [401, 403]:
            # Perfect! This proves wsproto is working.
            # The server successfully:
            # 1. Received the websocket upgrade request
            # 2. Processed it through wsproto
            # 3. Returned a proper HTTP auth error
            # This is exactly what we want to see.
            pass
        elif status == 404:
            pytest.fail(f"Websocket endpoint not found: {ws_url}")
        else:
            pytest.fail(f"Unexpected HTTP status during handshake: {status}")

    except websockets.exceptions.WebSocketException as e:
        # Other websocket-specific errors
        pytest.fail(f"Websocket protocol error: {type(e).__name__}: {e}")

    except Exception as e:
        # Network or other errors that indicate wsproto isn't working
        pytest.fail(
            f"Connection failed (wsproto may not be working): {type(e).__name__}: {e}"
        )
