"""Integration test to verify uvicorn works properly with wsproto.

This test actually starts uvicorn with wsproto and connects to it with a
real websocket client to ensure the integration works correctly.
"""

import json
import multiprocessing
import socket
import time

import pytest
import uvicorn
import websockets
from fastapi import FastAPI, WebSocket


def find_free_port():
    """Find a free port to use for the test server."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


def create_test_app():
    """Create a minimal FastAPI app with websocket endpoints for testing."""
    app = FastAPI()

    @app.websocket("/ws/echo")
    async def websocket_echo_endpoint(websocket: WebSocket):
        await websocket.accept()
        try:
            while True:
                data = await websocket.receive_text()
                await websocket.send_text(f"Echo: {data}")
        except Exception:
            pass

    @app.websocket("/ws/json")
    async def websocket_json_endpoint(websocket: WebSocket):
        await websocket.accept()
        try:
            while True:
                data = await websocket.receive_json()
                await websocket.send_json({"received": data})
        except Exception:
            pass

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


def run_uvicorn_server(port):
    """Run uvicorn server with wsproto in a separate process."""
    app = create_test_app()
    uvicorn.run(app, host="127.0.0.1", port=port, ws="wsproto", log_level="error")


@pytest.fixture
def uvicorn_server():
    """Start a uvicorn server with wsproto for testing."""
    port = find_free_port()
    process = multiprocessing.Process(target=run_uvicorn_server, args=(port,))
    process.start()

    # Wait for server to be ready
    max_wait = 5
    start_time = time.time()
    server_ready = False
    while time.time() - start_time < max_wait:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(("127.0.0.1", port))
            sock.close()
            if result == 0:
                server_ready = True
                break
        except Exception:
            pass
        time.sleep(0.1)

    if not server_ready:
        process.terminate()
        process.join()
        pytest.fail(f"Server failed to start on port {port} within {max_wait} seconds")

    yield port

    # Cleanup
    process.terminate()
    process.join(timeout=5)
    if process.is_alive():
        process.kill()
        process.join()


@pytest.mark.asyncio
async def test_uvicorn_wsproto_text_communication(uvicorn_server):
    """Test text websocket communication with real uvicorn+wsproto.

    This test actually connects to a running uvicorn server configured
    with wsproto to verify the integration works correctly.
    """
    port = uvicorn_server
    uri = f"ws://127.0.0.1:{port}/ws/echo"

    async with websockets.connect(uri) as websocket:
        # Test single message
        await websocket.send("Hello")
        response = await websocket.recv()
        assert response == "Echo: Hello"

        # Test multiple messages to verify protocol stability
        for i in range(3):
            await websocket.send(f"Message {i}")
            response = await websocket.recv()
            assert response == f"Echo: Message {i}"


@pytest.mark.asyncio
async def test_uvicorn_wsproto_json_communication(uvicorn_server):
    """Test JSON websocket communication with real uvicorn+wsproto.

    This verifies that wsproto correctly handles JSON message framing
    in a real uvicorn server environment.
    """
    port = uvicorn_server
    uri = f"ws://127.0.0.1:{port}/ws/json"

    async with websockets.connect(uri) as websocket:
        # Test JSON message handling
        test_data = {"message": "test", "value": 42}
        await websocket.send(json.dumps(test_data))
        response = json.loads(await websocket.recv())
        assert response["received"] == test_data

        # Test multiple JSON messages
        for i in range(2):
            data = {"id": i}
            await websocket.send(json.dumps(data))
            response = json.loads(await websocket.recv())
            assert response["received"]["id"] == i
