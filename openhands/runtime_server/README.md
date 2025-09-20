# OpenHands Runtime Server

A lightweight REST API for starting, pausing, resuming, and stopping Docker-based runtimes. Built with FastAPI and the Docker Python SDK.

## Endpoints

- `POST /start` — Launch a container based on a Docker image. Accepts environment variables, port bindings, and volume mounts. Returns the assigned `runtime_id`, container metadata, and published ports.
- `POST /pause` — Pause a running container by `runtime_id`.
- `POST /resume` — Resume a paused container by `runtime_id`.
- `POST /stop` — Stop a running container by `runtime_id`. An optional `timeout` field allows graceful shutdown before the container is forcibly terminated.

All request and response payloads are validated using Pydantic models for improved ergonomics and stability.

## Running the server

```bash
uv run runtime-server
```

Environment variables:

- `RUNTIME_SERVER_HOST` (default `0.0.0.0`)
- `RUNTIME_SERVER_PORT` (default `8090`)

When starting runtimes, the server ensures containers run in detached mode and tags each container with an internal label so subsequent lifecycle actions can reliably look them up.

## Client SDK

Use the bundled synchronous client to exercise the API from Python:

```python
from httpx import ASGITransport, Client

from openhands.runtime_server import RuntimeServerClient
from openhands.runtime_server.api import api


# In tests you can run against the FastAPI app directly with ASGITransport
transport = ASGITransport(app=api)
with Client(transport=transport, base_url="http://testserver") as http_client:
    client = RuntimeServerClient(base_url="http://testserver", http_client=http_client)
    try:
        client.start_runtime({
            "image": "busybox",
        })
    except Exception as exc:
        print(f"Expected failure without Docker backend: {exc}")
```

For real hosts, supply the runtime-server base URL (for example `http://localhost:8090`) and call `start_runtime`, `pause_runtime`, `resume_runtime`, or `stop_runtime` with dictionaries or typed Pydantic request objects.
