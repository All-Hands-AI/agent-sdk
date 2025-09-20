from __future__ import annotations

import os

import uvicorn


def _get_env(name: str, default: str) -> str:
    value = os.environ.get(name)
    return value if value is not None else default


def main() -> None:
    host = _get_env("RUNTIME_SERVER_HOST", "0.0.0.0")
    port = int(_get_env("RUNTIME_SERVER_PORT", "8090"))
    uvicorn.run("openhands.runtime_server.api:api", host=host, port=port)


if __name__ == "__main__":
    main()
