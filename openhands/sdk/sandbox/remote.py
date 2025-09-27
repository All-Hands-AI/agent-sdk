"""Remote sandboxed agent server implementation."""

from __future__ import annotations

import json
import time
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.request import urlopen

import httpx
import tenacity

from openhands.sdk.logger import get_logger
from openhands.sdk.sandbox.base import BashExecutionResult, SandboxedAgentServer
from openhands.sdk.sandbox.port_utils import find_available_tcp_port


logger = get_logger(__name__)


class RemoteSandboxedAgentServer(SandboxedAgentServer):
    """Run the Agent Server using a remote runtime API for sandboxed development.

    This implementation uses the OpenHands remote runtime API to start an agent server
    in a remote sandboxed environment, similar to how RemoteRuntime works but for
    the agent server instead of the runtime.

    Example:
        with RemoteSandboxedAgentServer(
            api_url="https://runtime-api.example.com",
            api_key="your-api-key",
            base_image="python:3.12",
            host_port=8010
        ) as server:
            # use server.base_url as the host for RemoteConversation
            conversation = Conversation(agent=agent, host=server.base_url)
            ...
    """

    def __init__(
        self,
        *,
        api_url: str,
        api_key: str,
        base_image: str,
        host_port: int | None = None,
        host: str = "127.0.0.1",
        session_id: str | None = None,
        resource_factor: int = 1,
        runtime_class: str | None = None,
        init_timeout: float = 300.0,
        api_timeout: float = 60.0,
        keep_alive: bool = False,
        pause_on_close: bool = False,
        **kwargs: Any,
    ) -> None:
        """Initialize the remote sandboxed agent server.

        Args:
            api_url: Base URL of the remote runtime API
            api_key: API key for authentication
            base_image: Base container image to use
            host_port: Port to bind the server to. If None, finds available port.
            host: Host interface to bind to. Defaults to localhost.
            session_id: Session ID for the runtime. If None, generates unique ID.
            resource_factor: Resource scaling factor for the runtime
            runtime_class: Runtime class to use (e.g., 'sysbox', 'gvisor')
            init_timeout: Timeout for runtime initialization in seconds
            api_timeout: Timeout for API requests in seconds
            keep_alive: Whether to keep the runtime alive after closing
            pause_on_close: Whether to pause the runtime instead of stopping it
            **kwargs: Additional arguments passed to parent class
        """
        super().__init__(host_port=host_port, host=host, **kwargs)
        self.host_port = int(host_port) if host_port else find_available_tcp_port()

        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.base_image = base_image
        self.session_id = session_id or f"agent-server-{int(time.time())}"
        if resource_factor not in [1, 2, 4, 8]:
            raise ValueError(
                f"resource_factor must be 1, 2, 4, or 8, got {resource_factor}"
            )
        self.resource_factor = resource_factor
        self.runtime_class = runtime_class
        self.init_timeout = init_timeout
        self.api_timeout = api_timeout
        self.keep_alive = keep_alive
        self.pause_on_close = pause_on_close

        # Runtime state
        self.runtime_id: str | None = None
        self.runtime_url: str | None = None
        self.session_api_key: str | None = None
        self._session: httpx.Client | None = None

    @property
    def session(self) -> httpx.Client:
        """Get or create the HTTP session for API requests."""
        if self._session is None:
            self._session = httpx.Client(
                headers={"X-API-Key": self.api_key}, timeout=self.api_timeout
            )
        return self._session

    def __enter__(self) -> RemoteSandboxedAgentServer:
        """Start the remote sandboxed agent server."""
        try:
            self._start_or_attach_to_runtime()
            self._wait_for_health()
            logger.info("Remote agent server is ready at %s", self.base_url)
            return self
        except Exception:
            self._cleanup()
            raise

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Stop the remote sandboxed agent server and clean up resources."""
        self._cleanup()

    def _start_or_attach_to_runtime(self) -> None:
        """Start or attach to an existing runtime."""
        logger.info("Starting or attaching to remote runtime")

        existing_runtime = self._check_existing_runtime()
        if existing_runtime:
            logger.info(f"Using existing runtime with ID: {self.runtime_id}")
        else:
            logger.info("No existing runtime found, starting a new one")
            self._start_runtime()

        assert self.runtime_id is not None, "Runtime ID is not set"
        assert self.runtime_url is not None, "Runtime URL is not set"

        # Set the base URL for the agent server
        # The agent server runs on port 8000 inside the runtime container
        # The runtime_url should already point to the correct endpoint
        self._base_url = self.runtime_url

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

        # Prepare the request body for the /start endpoint
        # The agent server should be built into the image and started as main process
        start_request: dict[str, Any] = {
            "image": self.base_image,
            "command": [
                "python",
                "-m",
                "openhands.agent_server",
                "--host",
                "0.0.0.0",
                "--port",
                "8000",
            ],
            "working_dir": "/workspace",
            "environment": {
                "LOG_JSON": "true",
            },
            "session_id": self.session_id,
            "resource_factor": self.resource_factor,
        }

        if self.runtime_class == "sysbox":
            start_request["runtime_class"] = "sysbox-runc"

        try:
            response = self._send_api_request(
                "POST", f"{self.api_url}/start", json=start_request
            )
            self._parse_runtime_response(response)
            logger.info(f"Runtime started. URL: {self.runtime_url}")
        except httpx.HTTPError as e:
            error_details = ""
            if hasattr(e, "response") and e.response is not None:  # type: ignore
                try:
                    error_details = f" - Response: {e.response.text}"  # type: ignore
                except Exception:
                    pass
            logger.error(f"Unable to start runtime: {str(e)}{error_details}")
            logger.error(f"Request payload: {start_request}")
            raise RuntimeError(
                f"Failed to start remote runtime: {e}{error_details}"
            ) from e

    def _resume_runtime(self) -> None:
        """Resume a paused runtime."""
        logger.info(f"Attempting to resume runtime with ID: {self.runtime_id}")

        try:
            response = self._send_api_request(
                "POST", f"{self.api_url}/resume", json={"runtime_id": self.runtime_id}
            )
            logger.info(
                f"Resume API call successful with status code: {response.status_code}"
            )
        except Exception as e:
            logger.error(f"Failed to call /resume API: {e}")
            raise

        logger.info("Runtime resume API call completed, waiting for it to be alive...")
        try:
            self._wait_until_runtime_alive()
            logger.info("Runtime is now alive after resume")
        except Exception as e:
            logger.error(f"Runtime failed to become alive after resume: {e}")
            raise

        logger.info("Runtime successfully resumed and alive.")

    def _parse_runtime_response(self, response: httpx.Response) -> None:
        """Parse the runtime response and extract runtime information."""
        data = response.json()
        self.runtime_id = data["runtime_id"]
        self.runtime_url = data["url"]

        if "session_api_key" in data:
            self.session_api_key = data["session_api_key"]
            if self.session_api_key:
                self.session.headers.update({"X-Session-API-Key": self.session_api_key})
                logger.debug("Session API key set")

    def _wait_until_runtime_alive(self) -> None:
        """Wait until the runtime is alive and ready."""
        retry_decorator = tenacity.retry(
            stop=tenacity.stop_after_delay(self.init_timeout),
            reraise=True,
            retry=tenacity.retry_if_exception_type(RuntimeError),
            wait=tenacity.wait_fixed(2),
        )
        retry_decorator(self._wait_until_runtime_alive_impl)()

    def _wait_until_runtime_alive_impl(self) -> None:
        """Implementation of runtime alive check."""
        logger.debug(f"Waiting for runtime to be alive at url: {self.runtime_url}")

        runtime_info_response = self._send_api_request(
            "GET", f"{self.api_url}/runtime/{self.runtime_id}"
        )
        runtime_data = runtime_info_response.json()

        assert "runtime_id" in runtime_data
        assert runtime_data["runtime_id"] == self.runtime_id
        assert "pod_status" in runtime_data

        pod_status = runtime_data["pod_status"].lower()
        logger.debug(f"Pod status: {pod_status}")

        restart_count = runtime_data.get("restart_count", 0)
        if restart_count != 0:
            restart_reasons = runtime_data.get("restart_reasons")
            logger.debug(f"Pod restarts: {restart_count}, reasons: {restart_reasons}")

        if pod_status == "ready":
            return
        elif pod_status in ("not found", "pending", "running"):
            raise RuntimeError(
                f"Runtime (ID={self.runtime_id}) is not yet ready. Status: {pod_status}"
            )
        elif pod_status in ("failed", "unknown", "crashloopbackoff"):
            if pod_status == "crashloopbackoff":
                raise RuntimeError(
                    "Runtime crashed and is being restarted, "
                    "potentially due to memory usage."
                )
            else:
                raise RuntimeError(
                    f"Runtime is unavailable (status: {pod_status}). Please try again."
                )
        else:
            logger.warning(f"Unknown pod status: {pod_status}")

        logger.debug(
            f"Waiting for runtime pod to be active. Current status: {pod_status}"
        )
        raise RuntimeError("Runtime not ready yet")

    def _wait_for_health(self, timeout: float = 120.0) -> None:
        """Wait for the agent server to become healthy and ready."""
        start = time.time()
        health_url = f"{self.base_url}/health"

        logger.info(f"Waiting for agent server health at: {health_url}")

        while time.time() - start < timeout:
            try:
                with urlopen(health_url, timeout=5.0) as resp:
                    if 200 <= getattr(resp, "status", 200) < 300:
                        logger.info("Agent server is healthy")
                        return
            except Exception as e:
                logger.debug(f"Health check failed: {e}")
                pass

            # Check if runtime is still running
            if self.runtime_id:
                try:
                    runtime_info_response = self._send_api_request(
                        "GET", f"{self.api_url}/runtime/{self.runtime_id}"
                    )
                    runtime_data = runtime_info_response.json()
                    pod_status = runtime_data.get("pod_status", "").lower()

                    if pod_status not in ("ready", "running"):
                        raise RuntimeError(
                            f"Runtime stopped unexpectedly. Status: {pod_status}"
                        )
                except Exception as e:
                    logger.error(f"Failed to check runtime status: {e}")
                    raise RuntimeError(
                        "Runtime became unavailable during health check"
                    ) from e

            time.sleep(2)

        raise RuntimeError("Agent server failed to become healthy in time")

    def _send_api_request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Send a request to the runtime API."""
        try:
            kwargs["timeout"] = self.api_timeout
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except httpx.TimeoutException:
            logger.error(
                f"No response received within the timeout period for url: {url}"
            )
            raise
        except httpx.HTTPError as e:
            logger.error(f"HTTP error for {method} {url}: {e}")
            raise

    def execute_bash(
        self, command: str, cwd: str | None = None, timeout: int = 300
    ) -> BashExecutionResult:
        """Execute a bash command in the remote sandboxed environment."""
        if self._base_url is None:
            raise RuntimeError("Server is not running")

        try:
            # Start the bash command
            response = self._send_api_request(
                "POST",
                f"{self._base_url}/api/bash/execute_bash_command",
                json={
                    "command": command,
                    "cwd": cwd,
                    "timeout": timeout,
                },
                timeout=timeout + 10,  # Add buffer to HTTP timeout
            )
            data = response.json()
            command_id = data["id"]

            # Wait for the command to complete and get results
            return self._wait_for_bash_completion(command_id, timeout)

        except Exception as e:
            logger.error(f"Failed to execute bash command: {e}")
            raise RuntimeError(f"Failed to execute bash command: {e}")

    def _wait_for_bash_completion(
        self, command_id: str, timeout: int = 300
    ) -> BashExecutionResult:
        """Wait for a bash command to complete and return the results."""
        import time

        start_time = time.time()
        poll_interval = 0.5  # Poll every 500ms

        while time.time() - start_time < timeout:
            try:
                # Search for bash events for this command
                response = self._send_api_request(
                    "GET",
                    f"{self._base_url}/api/bash/bash_events/search",
                    params={
                        "command_id__eq": command_id,
                        "kind__eq": "BashOutput",
                        "limit": 100,
                    },
                    timeout=10,
                )
                data = response.json()

                # Look for the final output (the one with exit_code)
                final_output = None
                all_outputs = []

                for item in data.get("items", []):
                    if item.get("command_id") == command_id:
                        all_outputs.append(item)
                        if item.get("exit_code") is not None:
                            final_output = item
                            break

                if final_output:
                    # Combine all output pieces
                    stdout_parts = []
                    stderr_parts = []

                    # Sort by order to ensure correct sequence
                    all_outputs.sort(key=lambda x: x.get("order", 0))

                    for output in all_outputs:
                        if output.get("stdout"):
                            stdout_parts.append(output["stdout"])
                        if output.get("stderr"):
                            stderr_parts.append(output["stderr"])

                    combined_output = "".join(stdout_parts)
                    if stderr_parts:
                        combined_stderr = "".join(stderr_parts)
                        if combined_output:
                            combined_output += "\n" + combined_stderr
                        else:
                            combined_output = combined_stderr

                    return BashExecutionResult(
                        command_id=command_id,
                        command=final_output.get("command", ""),
                        exit_code=final_output["exit_code"],
                        output=combined_output,
                    )

                # Command still running, wait and poll again
                time.sleep(poll_interval)

            except Exception as e:
                logger.debug(f"Error polling for bash results: {e}")
                time.sleep(poll_interval)

        # Timeout reached
        raise RuntimeError(f"Bash command timed out after {timeout} seconds")

    def upload_file(self, local_path: str | Path, remote_path: str) -> bool:
        """Upload a file to the remote sandboxed environment."""
        if self._base_url is None:
            raise RuntimeError("Server is not running")

        local_path = Path(local_path)
        if not local_path.exists():
            raise RuntimeError(f"Local file does not exist: {local_path}")

        try:
            with open(local_path, "rb") as f:
                files = {"file": (local_path.name, f, "application/octet-stream")}
                self._send_api_request(
                    "POST",
                    f"{self._base_url}/api/file/upload/{remote_path}",
                    files=files,
                    timeout=60,
                )
                return True
        except Exception as e:
            logger.error(f"Failed to upload file: {e}")
            return False

    def upload_file_content(self, content: str | bytes, remote_path: str) -> bool:
        """Upload file content to the remote sandboxed environment."""
        if self._base_url is None:
            raise RuntimeError("Server is not running")

        try:
            if isinstance(content, str):
                content_bytes = content.encode("utf-8")
            else:
                content_bytes = content

            files = {
                "file": ("content", BytesIO(content_bytes), "application/octet-stream")
            }
            self._send_api_request(
                "POST",
                f"{self._base_url}/api/file/upload/{remote_path}",
                files=files,
                timeout=60,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to upload file content: {e}")
            return False

    def download_file(
        self, remote_path: str, local_path: str | Path | None = None
    ) -> bytes | None:
        """Download a file from the remote sandboxed environment."""
        if self._base_url is None:
            raise RuntimeError("Server is not running")

        try:
            response = self._send_api_request(
                "GET",
                f"{self._base_url}/api/file/download/{remote_path}",
                timeout=60,
            )
            content = response.content

            if local_path is not None:
                local_path = Path(local_path)
                local_path.parent.mkdir(parents=True, exist_ok=True)
                with open(local_path, "wb") as f:
                    f.write(content)
                return None
            else:
                return content
        except Exception as e:
            logger.error(f"Failed to download file: {e}")
            if local_path is None:
                return None
            raise RuntimeError(f"Failed to download file: {e}")

    def _cleanup(self) -> None:
        """Clean up resources."""
        if self.runtime_id and not self.keep_alive:
            try:
                if self.pause_on_close:
                    self._send_api_request(
                        "POST",
                        f"{self.api_url}/pause",
                        json={"runtime_id": self.runtime_id},
                    )
                    logger.info("Runtime paused.")
                else:
                    self._send_api_request(
                        "POST",
                        f"{self.api_url}/stop",
                        json={"runtime_id": self.runtime_id},
                    )
                    logger.info("Runtime stopped.")
            except Exception as e:
                logger.error(f"Unable to stop/pause runtime: {str(e)}")

        if self._session:
            try:
                self._session.close()
            except Exception:
                pass
            self._session = None

        # Reset state
        self._base_url = None
        self.runtime_id = None
        self.runtime_url = None
        self.session_api_key = None
