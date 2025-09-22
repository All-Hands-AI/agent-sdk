"""
Script which demonstrates the use of the agent server with another server
acting as an example to accept webhook callbacks.

Start a conversation at:
http://localhost:8000/docs#/default/start_conversation_api_conversations__post

The current webhook requests are visible at:
http://localhost:8001/requests
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


webhook_example_client_api = FastAPI(title="Example Logging Webhook Client")
requests = []


@webhook_example_client_api.get("/requests")
async def display_requests():
    """Display the requests which have been sent to the example webhook client"""
    return JSONResponse(requests)


@webhook_example_client_api.delete("/requests")
async def clear_logs() -> bool:
    """Clear all requests which have been sent to the example webhook client"""
    global requests
    requests = []
    return True


@webhook_example_client_api.post("/{full_path:path}")
async def invoke_webhook(full_path: str, request: Request):
    """Invoke a webhook"""
    body = await request.json()
    requests.append(
        {
            "path": full_path,
            "body": body,
        }
    )


def main():
    # parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    # Run agent server
    port = args.port
    env = {**os.environ}
    env["OPENHANDS_AGENT_SERVER_CONFIG_PATH"] = "config.json"
    subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "openhands.agent_server.api:api",
            "--host",
            args.host,
            "--port",
            str(port),
        ],
        cwd=str(Path(__file__).parent),
        env=env,
    )

    # Run webhook client
    uvicorn.run(webhook_example_client_api, host=args.host, port=port + 1)


if __name__ == "__main__":
    main()
