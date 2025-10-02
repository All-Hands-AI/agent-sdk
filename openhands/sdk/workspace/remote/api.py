"""API-based remote workspace implementation using runtime API."""

import json
import time
from typing import Any
from urllib.request import urlopen

import httpx
import tenacity
from pydantic import Field, PrivateAttr

from openhands.sdk.logger import get_logger
from openhands.sdk.workspace.remote.base import RemoteWorkspace


logger = get_logger(__name__)


class APIRemoteWorkspace(RemoteWorkspace):
    """Remote workspace that provisions a runtime via the OpenHands runtime API.

    This workspace uses the OpenHands remote runtime API to start an agent server
    in a remote sandboxed environment. It handles runtime provisioning, lifecycle
    management, and provides remote workspace operations through the runtime's API.

    Example:
        workspace = APIRemoteWorkspace(
            api_url="https://runtime-api.example.com",
            runtime_api_key="your-api-key",
            base_image="python:3.12",
            working_dir="/workspace",
            session_id="my-session"
        )
        result = workspace.execute_command("ls -la")
    """

    api_url: str = Field(description="Base URL of the remote runtime API")
    runtime_api_key: str = Field(description="API key for runtime API authentication")
    base_image: str = Field(description="Base container image to use")
    session_id: str | None = Field(
        default=None, description="Session ID for the runtime. Auto-generated if None."
    )
    resource_factor: int = Field(
        default=1, description="Resource scaling factor (1, 2, 4, or 8)"
    )
    runtime_class: str | None = Field(
        default=None, description="Runtime class (e.g., 'sysbox', 'gvisor')"
    )
    init_timeout: float = Field(
        default=300.0, description="Timeout for runtime initialization in seconds"
    )
    api_timeout: float = Field(
        default=60.0, description="Timeout for API requests in seconds"
    )
    keep_alive: bool = Field(
        default=False, description="Keep runtime alive after workspace is destroyed"
    )
    pause_on_close: bool = Field(
        default=False, description="Pause runtime instead of stopping it on cleanup"
    )

    _runtime_id: str | None = PrivateAttr(default=None)
    _runtime_url: str | None = PrivateAttr(default=None)
    _session_api_key: str | None = PrivateAttr(default=None)
    _api_session: httpx.Client = PrivateAttr()

    def model_post_init(self, context: Any) -> None:
        """Set up the remote runtime and initialize the workspace."""
        # Generate session ID if not provided
        if self.session_id is None:
            object.__setattr__(self, "session_id", f"agent-server-{int(time.time())}")

        # Validate resource_factor
        if self.resource_factor not in [1, 2, 4, 8]:
            raise ValueError(
                f"resource_factor must be 1, 2, 4, or 8, got {self.resource_factor}"
            )

        # Create API session for runtime management
        self._api_session = httpx.Client(
            headers={"X-API-Key": self.runtime_api_key}, timeout=self.api_timeout
        )

        # Clean up API URL
        object.__setattr__(self, "api_url", self.api_url.rstrip("/"))

        # Start or attach to runtime
        try:
            self._start_or_attach_to_runtime()
            logger.info("Remote runtime workspace is ready at %s", self.host)

            # Now initialize the parent RemoteWorkspace with the runtime URL
            super().model_post_init(context)
        except Exception:
            self.cleanup()
            raise

    def _start_or_attach_to_runtime(self) -> None:
        """Start or attach to an existing runtime."""
        logger.info("Starting or attaching to remote runtime")

        existing_runtime = self._check_existing_runtime()
        if existing_runtime:
            logger.info(f"Using existing runtime with ID: {self._runtime_id}")
        else:
            logger.info("No existing runtime found, starting a new one")
            self._start_runtime()

        assert self._runtime_id is not None, "Runtime ID is not set"
        assert self._runtime_url is not None, "Runtime URL is not set"

        # Set host and api_key for RemoteWorkspace to use
        object.__setattr__(self, "host", self._runtime_url)
        object.__setattr__(self, "api_key", self._session_api_key)

        logger.info("Waiting for runtime to be alive...")
        self._wait_until_runtime_alive()
        logger.info("Runtime is ready.")

    def _check_existing_runtime(self) -> bool:
        """Check if there's an existing runtime for this session."""
        logger.info(f"Checking for existing runtime with session ID: {self.session_id}")

        try:
            response = self._send_api_request(
                "GET", f"{self.api_url}/sessions/{self.session_id}"
            )
            data = response.json()
            status = data.get("status")
            logger.info(f"Found runtime with status: {status}")

            if status in ("running", "paused"):
                self._parse_runtime_response(response)

                if status == "running":
                    logger.info("Found existing runtime in running state")
                    return True
                elif status == "paused":
                    logger.info(
                        "Found existing runtime in paused state, attempting to resume"
                    )
                    try:
                        self._resume_runtime()
                        logger.info("Successfully resumed paused runtime")
                        return True
                    except Exception as e:
                        logger.error(f"Failed to resume paused runtime: {e}")
                        return False
            elif status == "stopped":
                logger.info("Found existing runtime, but it is stopped")
                return False
            else:
                logger.error(f"Invalid response from runtime API: {data}")
                return False

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.info(
                    f"No existing runtime found for session ID: {self.session_id}"
                )
                return False
            logger.error(f"Error while looking for remote runtime: {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response from runtime API: {e}")
            raise

        return False

    def _start_runtime(self) -> None:
        """Start a new runtime."""
        logger.info(f"Starting new runtime with image: {self.base_image}")

        payload: dict[str, Any] = {
            "image": self.base_image,
            "command": [
                "/openhands/micromamba/bin/python",
                "-m",
                "openhands.agent_server.server",
                "--host",
                "0.0.0.0",
                "--port",
                "8000",
            ],
        }

        if self.runtime_class:
            payload["runtime_class"] = self.runtime_class

        if self.resource_factor != 1:
            payload["resource_factor"] = self.resource_factor

        logger.info(f"Creating runtime with payload: {payload}")

        response = self._send_api_request(
            "PUT",
            f"{self.api_url}/sessions/{self.session_id}",
            json=payload,
            timeout=self.init_timeout,
        )

        logger.info(f"Runtime created with status {response.status_code}")
        self._parse_runtime_response(response)

        logger.info(
            f"Runtime started with ID {self._runtime_id} at {self._runtime_url}"
        )

    def _resume_runtime(self) -> None:
        """Resume a paused runtime."""
        logger.info(f"Resuming runtime with session ID: {self.session_id}")

        response = self._send_api_request(
            "POST",
            f"{self.api_url}/sessions/{self.session_id}/resume",
            timeout=self.init_timeout,
        )

        logger.info(f"Runtime resumed with status {response.status_code}")
        self._parse_runtime_response(response)

        logger.info(
            f"Runtime resumed with ID {self._runtime_id} at {self._runtime_url}"
        )

    def _parse_runtime_response(self, response: httpx.Response) -> None:
        """Parse the runtime response and extract connection info."""
        data = response.json()
        self._runtime_id = data.get("id")
        self._runtime_url = data.get("url")
        self._session_api_key = data.get("api_key")

        if not self._runtime_id or not self._runtime_url:
            raise ValueError(f"Invalid runtime response: {data}")

    @tenacity.retry(
        stop=tenacity.stop_after_delay(120),
        wait=tenacity.wait_exponential(multiplier=1, min=2, max=10),
        retry=tenacity.retry_if_exception_type(Exception),
        reraise=True,
    )
    def _wait_until_runtime_alive(self) -> None:
        """Wait until the runtime becomes alive and responsive."""
        assert self._runtime_url is not None, "Runtime URL is not set"

        health_url = f"{self._runtime_url}/health"
        logger.debug(f"Checking runtime health at {health_url}")

        try:
            with urlopen(health_url, timeout=5.0) as resp:
                status = getattr(resp, "status", 200)
                if 200 <= status < 300:
                    logger.info("Runtime is alive and healthy")
                    return
                logger.warning(f"Runtime health check returned status {status}")
                raise RuntimeError(f"Runtime health check failed with status {status}")
        except Exception as e:
            logger.debug(f"Runtime not yet alive: {e}")
            raise

    def _send_api_request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Send an API request with error handling."""
        logger.debug(f"{method} {url}")
        response = self._api_session.request(method, url, **kwargs)
        response.raise_for_status()
        return response

    def cleanup(self) -> None:
        """Clean up the remote runtime."""
        if not self._runtime_id:
            return

        try:
            if self.keep_alive:
                logger.info(
                    f"Keeping runtime {self._runtime_id} alive (keep_alive=True)"
                )
                return

            if self.pause_on_close:
                logger.info(f"Pausing runtime {self._runtime_id}")
                self._send_api_request(
                    "POST",
                    f"{self.api_url}/sessions/{self.session_id}/pause",
                    timeout=30.0,
                )
            else:
                logger.info(f"Stopping runtime {self._runtime_id}")
                self._send_api_request(
                    "DELETE",
                    f"{self.api_url}/sessions/{self.session_id}",
                    timeout=30.0,
                )
        except Exception as e:
            logger.error(f"Error cleaning up runtime: {e}")
        finally:
            self._runtime_id = None
            self._runtime_url = None
            self._session_api_key = None

            if self._api_session:
                try:
                    self._api_session.close()
                except Exception:
                    pass

    def __del__(self) -> None:
        """Clean up the runtime when the workspace is destroyed."""
        self.cleanup()

    def __enter__(self) -> "APIRemoteWorkspace":
        """Enter context manager."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager and clean up resources."""
        self.cleanup()
