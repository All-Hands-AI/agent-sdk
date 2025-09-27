from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
import threading
import time
from collections.abc import Iterable
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.request import urlopen

import httpx

from openhands.sdk.logger import get_logger
from openhands.sdk.sandbox.base import BashExecutionResult, SandboxedAgentServer
from openhands.sdk.sandbox.port_utils import find_available_tcp_port


logger = get_logger(__name__)


def _run(
    cmd: list[str] | str,
    env: dict[str, str] | None = None,
    cwd: str | None = None,
) -> subprocess.CompletedProcess:
    if isinstance(cmd, str):
        cmd_list = shlex.split(cmd)
    else:
        cmd_list = cmd
    logger.info("$ %s", " ".join(shlex.quote(c) for c in cmd_list))

    proc = subprocess.Popen(
        cmd_list,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    if proc is None:
        raise RuntimeError("Failed to start process")

    # Read line by line, echo to parent stdout/stderr
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    if proc.stdout is None or proc.stderr is None:
        raise RuntimeError("Failed to capture stdout/stderr")

    for line in proc.stdout:
        sys.stdout.write(line)
        stdout_lines.append(line)
    for line in proc.stderr:
        sys.stderr.write(line)
        stderr_lines.append(line)

    proc.wait()

    return subprocess.CompletedProcess(
        cmd_list,
        proc.returncode,
        "".join(stdout_lines),
        "".join(stderr_lines),
    )


def _parse_build_tags(build_stdout: str) -> list[str]:
    # build.sh prints at the end:
    # [build] Done. Tags:
    #  - <tag1>
    #  - <tag2>
    tags: list[str] = []
    collecting = False
    for ln in build_stdout.splitlines():
        if "[build] Done. Tags:" in ln:
            collecting = True
            continue
        if collecting:
            m = re.match(r"\s*-\s*(\S+)$", ln)
            if m:
                tags.append(m.group(1))
            elif ln.strip():
                break
    return tags


def _resolve_build_script() -> Path | None:
    # Prefer locating via importlib without importing the module
    try:
        import importlib.util

        spec = importlib.util.find_spec("openhands.agent_server")
        if spec and spec.origin:
            p = Path(spec.origin).parent / "docker" / "build.sh"
            if p.exists():
                return p
    except Exception:
        pass

    # Try common project layouts relative to this file and CWD
    candidates: list[Path] = [
        Path(__file__).resolve().parents[3]
        / "openhands"
        / "agent_server"
        / "docker"
        / "build.sh",
        Path.cwd() / "openhands" / "agent_server" / "docker" / "build.sh",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def build_agent_server_image(
    base_image: str,
    target: str = "source",
    variant_name: str = "custom",
    platforms: str = "linux/amd64",
    extra_env: dict[str, str] | None = None,
    project_root: str | None = None,
) -> str:
    """Build the agent-server Docker image via the repo's build.sh.

    This is a dev convenience that shells out to the build script provided in
    openhands/agent_server/docker/build.sh. Returns the first image tag printed
    by the script.

    If the script cannot be located, raise a helpful error. In that case,
    users can manually provide an image to DockerSandboxedAgentServer(image="...").
    """
    script_path = _resolve_build_script()
    if not script_path:
        raise FileNotFoundError(
            "Could not locate openhands/agent_server/docker/build.sh. "
            "Ensure you're running in the OpenHands repo or pass an explicit "
            "image to DockerSandboxedAgentServer(image=...)."
        )

    env = os.environ.copy()
    env["BASE_IMAGE"] = base_image
    env["VARIANT_NAME"] = variant_name
    env["TARGET"] = target
    env["PLATFORMS"] = platforms
    logger.info(
        "Building agent-server image with base '%s', target '%s', "
        "variant '%s' for platforms '%s'",
        base_image,
        target,
        variant_name,
        platforms,
    )

    if extra_env:
        env.update(extra_env)

    # Default project root is repo root (two levels above openhands/)
    if not project_root:
        project_root = str(Path(__file__).resolve().parents[3])

    proc = _run(["bash", str(script_path)], env=env, cwd=project_root)

    if proc.returncode != 0:
        msg = (
            f"build.sh failed with exit code {proc.returncode}.\n"
            f"STDOUT:\n{proc.stdout}\n"
            f"STDERR:\n{proc.stderr}"
        )
        raise RuntimeError(msg)

    tags = _parse_build_tags(proc.stdout)
    if not tags:
        raise RuntimeError(
            f"Failed to parse image tags from build output.\nSTDOUT:\n{proc.stdout}"
        )

    image = tags[0]
    logger.info("Using image: %s", image)
    return image


class DockerSandboxedAgentServer(SandboxedAgentServer):
    """Run the Agent Server inside Docker for sandboxed development.

    Example:
        with DockerSandboxedAgentServer(
            base_image="python:3.12", host_port=8010
        ) as srv:
            # use server.base_url as the host for RemoteConversation
            ...
    """

    def __init__(
        self,
        *,
        base_image: str,
        host_port: int | None = None,
        host: str = "127.0.0.1",
        forward_env: Iterable[str] | None = None,
        mount_dir: str | None = None,
        detach_logs: bool = True,
        target: str = "source",
        platform: str = "linux/amd64",
        **kwargs: Any,
    ) -> None:
        super().__init__(host_port=host_port, host=host, **kwargs)
        self.host_port = int(host_port) if host_port else find_available_tcp_port()
        self._image = base_image
        self.container_id: str | None = None
        self._logs_thread: threading.Thread | None = None
        self._stop_logs = threading.Event()
        self.mount_dir = mount_dir
        self.detach_logs = detach_logs
        self._forward_env = list(forward_env or ["DEBUG"])
        self._target = target
        self._platform = platform

    def __enter__(self) -> DockerSandboxedAgentServer:
        # Ensure docker exists
        docker_ver = _run(["docker", "version"]).returncode
        if docker_ver != 0:
            raise RuntimeError(
                "Docker is not available. Please install and start "
                "Docker Desktop/daemon."
            )

        # Build if base image is provided, BUT not if
        # it's not an pre-built official image
        if self._image and "ghcr.io/all-hands-ai/agent-server" not in self._image:
            self._image = build_agent_server_image(
                base_image=self._image,
                target=self._target,
                # we only support single platform for now
                platforms=self._platform,
            )

        # Prepare env flags
        flags: list[str] = []
        for key in self._forward_env:
            if key in os.environ:
                flags += ["-e", f"{key}={os.environ[key]}"]

        # Prepare mount flags
        if self.mount_dir:
            mount_path = "/workspace"
            flags += ["-v", f"{self.mount_dir}:{mount_path}"]
            logger.info(
                "Mounting host dir %s to container path %s", self.mount_dir, mount_path
            )

        # Run container
        run_cmd = [
            "docker",
            "run",
            "-d",
            "--platform",
            self._platform,
            "--rm",
            "--name",
            f"agent-server-{int(time.time())}",
            "-p",
            f"{self.host_port}:8000",
            *flags,
            self._image,
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
        ]
        proc = _run(run_cmd)
        if proc.returncode != 0:
            raise RuntimeError(f"Failed to run docker container: {proc.stderr}")

        self.container_id = proc.stdout.strip()
        logger.info("Started container: %s", self.container_id)

        # Optionally stream logs in background
        if self.detach_logs:
            self._logs_thread = threading.Thread(
                target=self._stream_docker_logs, daemon=True
            )
            self._logs_thread.start()

        # Set the base URL for the abstract base class
        self._base_url = f"http://{self.host}:{self.host_port}"

        # Wait for health
        self._wait_for_health()
        logger.info("API server is ready at %s", self.base_url)
        return self

    def _stream_docker_logs(self) -> None:
        if not self.container_id:
            return
        try:
            p = subprocess.Popen(
                ["docker", "logs", "-f", self.container_id],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            if p.stdout is None:
                return
            for line in iter(p.stdout.readline, ""):
                if self._stop_logs.is_set():
                    break
                if line:
                    sys.stdout.write(f"[DOCKER] {line}")
                    sys.stdout.flush()
        except Exception as e:
            sys.stderr.write(f"Error streaming docker logs: {e}\n")
        finally:
            try:
                self._stop_logs.set()
            except Exception:
                pass

    def _wait_for_health(self, timeout: float = 120.0) -> None:
        start = time.time()
        health_url = f"{self.base_url}/health"

        while time.time() - start < timeout:
            try:
                with urlopen(health_url, timeout=1.0) as resp:
                    if 200 <= getattr(resp, "status", 200) < 300:
                        return
            except Exception:
                pass
            # Check if container is still running
            if self.container_id:
                ps = _run(
                    ["docker", "inspect", "-f", "{{.State.Running}}", self.container_id]
                )
                if ps.stdout.strip() != "true":
                    logs = _run(["docker", "logs", self.container_id])
                    msg = (
                        "Container stopped unexpectedly. Logs:\n"
                        f"{logs.stdout}\n{logs.stderr}"
                    )
                    raise RuntimeError(msg)
            time.sleep(1)
        raise RuntimeError("Server failed to become healthy in time")

    def execute_bash(
        self, command: str, cwd: str | None = None, timeout: int = 300
    ) -> BashExecutionResult:
        """Execute a bash command in the Docker container."""
        if self._base_url is None:
            raise RuntimeError("Server is not running")

        try:
            with httpx.Client() as client:
                # Start the bash command
                response = client.post(
                    f"{self._base_url}/api/bash/execute_bash_command",
                    json={
                        "command": command,
                        "cwd": cwd,
                        "timeout": timeout,
                    },
                    timeout=timeout + 10,  # Add buffer to HTTP timeout
                )
                response.raise_for_status()
                data = response.json()
                command_id = data["id"]

                # Wait for the command to complete and get results
                return self._wait_for_bash_completion(client, command_id, timeout)

        except Exception as e:
            logger.error(f"Failed to execute bash command: {e}")
            raise RuntimeError(f"Failed to execute bash command: {e}")

    def _wait_for_bash_completion(
        self, client: httpx.Client, command_id: str, timeout: int = 300
    ) -> BashExecutionResult:
        """Wait for a bash command to complete and return the results."""
        import time

        start_time = time.time()
        poll_interval = 0.5  # Poll every 500ms

        while time.time() - start_time < timeout:
            try:
                # Search for bash events for this command
                response = client.get(
                    f"{self._base_url}/api/bash/bash_events/search",
                    params={
                        "command_id__eq": command_id,
                        "kind__eq": "BashOutput",
                        "limit": 100,
                    },
                    timeout=10,
                )
                response.raise_for_status()
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
        """Upload a file to the Docker container."""
        if self._base_url is None:
            raise RuntimeError("Server is not running")

        local_path = Path(local_path)
        if not local_path.exists():
            raise RuntimeError(f"Local file does not exist: {local_path}")

        try:
            with httpx.Client() as client:
                with open(local_path, "rb") as f:
                    files = {"file": (local_path.name, f, "application/octet-stream")}
                    response = client.post(
                        f"{self._base_url}/api/file/upload/{remote_path}",
                        files=files,
                        timeout=60,
                    )
                    response.raise_for_status()
                    return True
        except Exception as e:
            logger.error(f"Failed to upload file: {e}")
            return False

    def upload_file_content(self, content: str | bytes, remote_path: str) -> bool:
        """Upload file content to the Docker container."""
        if self._base_url is None:
            raise RuntimeError("Server is not running")

        try:
            if isinstance(content, str):
                content_bytes = content.encode("utf-8")
            else:
                content_bytes = content

            with httpx.Client() as client:
                files = {
                    "file": (
                        "content",
                        BytesIO(content_bytes),
                        "application/octet-stream",
                    )
                }
                response = client.post(
                    f"{self._base_url}/api/file/upload/{remote_path}",
                    files=files,
                    timeout=60,
                )
                response.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Failed to upload file content: {e}")
            return False

    def download_file(
        self, remote_path: str, local_path: str | Path | None = None
    ) -> bytes | None:
        """Download a file from the Docker container."""
        if self._base_url is None:
            raise RuntimeError("Server is not running")

        try:
            with httpx.Client() as client:
                response = client.get(
                    f"{self._base_url}/api/file/download/{remote_path}",
                    timeout=60,
                )
                response.raise_for_status()
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

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.container_id:
            try:
                _run(["docker", "rm", "-f", self.container_id])
            except Exception:
                pass
        if self._logs_thread:
            try:
                self._stop_logs.set()
                self._logs_thread.join(timeout=2)
            except Exception:
                pass
        # Reset base URL
        self._base_url = None
