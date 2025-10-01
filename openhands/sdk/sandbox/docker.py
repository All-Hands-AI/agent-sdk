from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Iterable
from pathlib import Path
from urllib.request import urlopen

from openhands.sdk.logger import get_logger
from openhands.sdk.sandbox.port_utils import (
    check_port_available,
    find_available_tcp_port,
)
from openhands.sdk.utils.command import execute_command


logger = get_logger(__name__)


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
    # Check if AGENT_SDK_PATH environment variable is set
    agent_sdk_path = os.environ.get("AGENT_SDK_PATH")
    if agent_sdk_path:
        p = Path(agent_sdk_path) / "openhands" / "agent_server" / "docker" / "build.sh"
        if p.exists():
            return p

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

    # Try common project layouts relative to CWD and this file
    candidates: list[Path] = [
        Path.cwd() / "openhands" / "agent_server" / "docker" / "build.sh",
        Path(__file__).resolve().parents[3]
        / "openhands"
        / "agent_server"
        / "docker"
        / "build.sh",
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

    proc = execute_command(["bash", str(script_path)], env=env, cwd=project_root)

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


class DockerSandboxedAgentServer:
    """Run the Agent Server inside Docker for sandboxed development.

    Example:
        with DockerSandboxedAgentServer(host_port=8010) as server:
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
        extra_ports: bool = False,
    ) -> None:
        self.host_port = int(host_port) if host_port else find_available_tcp_port()
        if not check_port_available(self.host_port):
            raise RuntimeError(f"Port {self.host_port} is not available")

        self._extra_ports = extra_ports
        if extra_ports:
            if not check_port_available(self.host_port + 1):
                raise RuntimeError(
                    f"Port {self.host_port + 1} is not available for VSCode"
                )
            if not check_port_available(self.host_port + 2):
                raise RuntimeError(
                    f"Port {self.host_port + 2} is not available for VNC"
                )

        self._image = base_image
        self.host = host
        self.base_url = f"http://{host}:{self.host_port}"
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
        docker_ver = execute_command(["docker", "version"]).returncode
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

        ports = ["-p", f"{self.host_port}:8000"]
        if self._extra_ports:
            ports += [
                "-p",
                f"{self.host_port + 1}:8001",  # VScode
                "-p",
                f"{self.host_port + 2}:8002",  # Desktop VNC
            ]
        flags += ports

        # Run container
        run_cmd = [
            "docker",
            "run",
            "-d",
            "--platform",
            self._platform,
            "--rm",
            "--name",
            f"agent-server-{uuid.uuid4()}",
            *flags,
            self._image,
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
        ]
        proc = execute_command(run_cmd)
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
                ps = execute_command(
                    ["docker", "inspect", "-f", "{{.State.Running}}", self.container_id]
                )
                if ps.stdout.strip() != "true":
                    logs = execute_command(["docker", "logs", self.container_id])
                    msg = (
                        "Container stopped unexpectedly. Logs:\n"
                        f"{logs.stdout}\n{logs.stderr}"
                    )
                    raise RuntimeError(msg)
            time.sleep(1)
        raise RuntimeError("Server failed to become healthy in time")

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.container_id:
            try:
                execute_command(["docker", "rm", "-f", self.container_id])
            except Exception:
                pass
        if self._logs_thread:
            try:
                self._stop_logs.set()
                self._logs_thread.join(timeout=2)
            except Exception:
                pass
