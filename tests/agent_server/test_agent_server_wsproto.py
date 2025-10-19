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


def run_agent_server(port):
    """Run the actual agent server using __main__.py."""
    # Import here to avoid issues with multiprocessing
    from openhands.agent_server.__main__ import main

    # Override sys.argv to set the port
    sys.argv = ["agent-server", "--port", str(port)]
    main()


@pytest.fixture
def agent_server():
    """Start the agent server for testing."""
    port = find_free_port()
    process = multiprocessing.Process(target=run_agent_server, args=(port,))
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
    proper websocket communication.
    """
    port = agent_server

    # Try to connect to the bash-events websocket endpoint
    # Note: This might require authentication in the actual server,
    # so we just verify we can attempt a connection and get a proper
    # websocket response (not an HTTP error)
    ws_url = f"ws://127.0.0.1:{port}/sockets/bash-events"

    try:
        async with websockets.connect(ws_url):
            # If we get here, the websocket connection succeeded
            # (authentication might still fail, but that's a different layer)
            pass
    except websockets.exceptions.InvalidStatus as e:
        # Server responded with HTTP status (e.g., 401/403 for auth errors)
        # This is expected if auth is required, but it proves websockets are working
        # The key is that the server is using wsproto to handle the websocket handshake
        assert e.response.status_code in [
            401,
            403,
        ], f"Unexpected HTTP status: {e.response.status_code}"
    except Exception as e:
        # Any other exception means websockets aren't working properly
        pytest.fail(f"Websocket connection failed: {e}")
