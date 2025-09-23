import os
import re
import shlex
import subprocess
import sys
import threading
import time
from pathlib import Path

from pydantic import SecretStr

from openhands.sdk import LLM, Conversation, get_logger
from openhands.sdk.conversation.impl.remote_conversation import RemoteConversation
from openhands.sdk.preset.default import get_default_agent


"""
Example 23: Hello World with a sandboxed Agent Server (Docker)

This example demonstrates how to:
  1) Build a DEV (source) Docker image of the OpenHands Agent Server
  2) Parse the resulting image tag
  3) Launch the Docker container with proper mounts and port mapping
  4) Connect to the server inside Docker and interact with it
  5) Run the same conversation flow as in example 22

Prerequisites:
  - Docker and docker buildx installed
  - LITELLM_API_KEY set in your shell env (used by the agent)

Notes:
  - We mount the current repo into /workspace inside the container so agent
    actions affect your local files, mirroring the behavior of example 22.
  - The dev image target runs the server from source with a virtualenv inside
    the container for quick iteration.
"""

logger = get_logger(__name__)


def _stream_output(stream, prefix, target_stream):
    try:
        for line in iter(stream.readline, ""):
            if line:
                target_stream.write(f"[{prefix}] {line}")
                target_stream.flush()
    except Exception as e:
        print(f"Error streaming {prefix}: {e}", file=sys.stderr)
    finally:
        try:
            stream.close()
        except Exception:
            pass


def _run(
    cmd: list[str] | str, env: dict | None = None, cwd: str | None = None
) -> subprocess.CompletedProcess:
    if isinstance(cmd, str):
        cmd_list = shlex.split(cmd)
    else:
        cmd_list = cmd
    logger.info(f"$ {' '.join(shlex.quote(c) for c in cmd_list)}")
    return subprocess.run(
        cmd_list, cwd=cwd, env=env, text=True, capture_output=True, check=False
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
                # stop if something else appears
                break
    return tags


def build_dev_image() -> str:
    """Build the dev (source) image via build.sh and return the primary tag.

    Returns the first tag printed by build.sh, which follows the format:
      ghcr.io/all-hands-ai/agent-server:<short_sha>-python-dev
    """
    script_path = (
        Path(__file__).resolve().parents[1]
        / "openhands"
        / "agent_server"
        / "docker"
        / "build.sh"
    )
    assert script_path.exists(), f"build.sh not found at {script_path}"

    env = os.environ.copy()
    env.setdefault("TARGET", "source")  # dev build
    env.setdefault("VARIANT_NAME", "python")

    # Run the build
    proc = _run(
        ["bash", str(script_path)],
        env=env,
        cwd=str(Path(__file__).resolve().parents[1]),
    )

    # Stream stderr for visibility if any
    if proc.stderr:
        for ln in proc.stderr.splitlines():
            logger.info(f"[build.sh:stderr] {ln}")

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
    logger.info(f"Using image: {image}")
    return image


class ManagedDockerAPIServer:
    """Context manager that builds the dev image, runs the server in Docker,
    and waits for health.
    """

    def __init__(
        self,
        host_port: int = 8010,
        mount_dir: str | None = None,
        image: str | None = None,
        host: str = "127.0.0.1",
        detach_logs: bool = True,
    ):
        self.host_port = int(host_port)
        self.mount_dir = mount_dir or os.getcwd()
        self.image = image
        self.host = host
        self.base_url = f"http://{host}:{self.host_port}"
        self.container_id: str | None = None
        self._logs_thread: threading.Thread | None = None
        self._stop_logs = threading.Event()
        self.detach_logs = detach_logs

    def __enter__(self):
        # Ensure docker exists
        docker_ver = _run(["docker", "version"]).returncode
        if docker_ver != 0:
            raise RuntimeError(
                "Docker is not available. Please install and start "
                "Docker Desktop/daemon."
            )

        # Build if no image provided
        if not self.image:
            self.image = build_dev_image()

        # Run container
        run_cmd = [
            "docker",
            "run",
            "-d",
            "--rm",
            "--name",
            f"agent-server-{int(time.time())}",
            "-p",
            f"{self.host_port}:8000",
            "-v",
            f"{self.mount_dir}:/workspace",
            self.image,
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
        ]
        proc = _run(run_cmd)
        if proc.returncode != 0:
            raise RuntimeError(f"Failed to run docker container: {proc.stderr}")

        self.container_id = proc.stdout.strip()
        logger.info(f"Started container: {self.container_id}")

        # Optionally stream logs in background
        if self.detach_logs:
            self._logs_thread = threading.Thread(
                target=self._stream_docker_logs, daemon=True
            )
            self._logs_thread.start()

        # Wait for health
        self._wait_for_health()
        logger.info(f"API server is ready at {self.base_url}")
        return self

    def _stream_docker_logs(self):
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

    def _wait_for_health(self, timeout: float = 120.0):
        start = time.time()
        import httpx

        while time.time() - start < timeout:
            try:
                r = httpx.get(f"{self.base_url}/health", timeout=1.0)
                if r.status_code == 200:
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

    def __exit__(self, exc_type, exc, tb):
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


def main():
    # 1) Ensure we have LLM API key
    api_key = os.getenv("LITELLM_API_KEY")
    assert api_key is not None, "LITELLM_API_KEY environment variable is not set."

    llm = LLM(
        model="litellm_proxy/anthropic/claude-sonnet-4-20250514",
        base_url="https://llm-proxy.eval.all-hands.dev",
        api_key=SecretStr(api_key),
    )

    # 2) Start the dev image in Docker and wait for health
    with ManagedDockerAPIServer(host_port=8010) as server:
        # 3) Create agent – IMPORTANT: working_dir must be the path inside container
        #    where we mounted the current repo.
        agent = get_default_agent(
            llm=llm,
            working_dir="/workspace",
            cli_mode=True,
        )

        # 4) Set up callback collection, like example 22
        received_events: list = []
        last_event_time = {"ts": time.time()}

        def event_callback(event):
            event_type = type(event).__name__
            logger.info(f"🔔 Callback received event: {event_type}\n{event}")
            received_events.append(event)
            last_event_time["ts"] = time.time()

        # 5) Create RemoteConversation and do the same 2-step task
        conversation = Conversation(
            agent=agent,
            host=server.base_url,
            callbacks=[event_callback],
            visualize=True,
        )
        assert isinstance(conversation, RemoteConversation)

        try:
            logger.info(f"\n📋 Conversation ID: {conversation.state.id}")
            logger.info("📝 Sending first message...")
            conversation.send_message(
                "Read the current repo and write 3 facts about the project into "
                "FACTS.txt."
            )
            logger.info("🚀 Running conversation...")
            conversation.run()
            logger.info("✅ First task completed!")
            logger.info(f"Agent status: {conversation.state.agent_status}")

            # Wait for events to settle (no events for 2 seconds)
            logger.info("⏳ Waiting for events to stop...")
            while time.time() - last_event_time["ts"] < 2.0:
                time.sleep(0.1)
            logger.info("✅ Events have stopped")

            logger.info("🚀 Running conversation again...")
            conversation.send_message("Great! Now delete that file.")
            conversation.run()
            logger.info("✅ Second task completed!")

            # Demonstrate state.events
            logger.info("\n" + "=" * 50)
            logger.info("📊 Demonstrating State Events API")
            logger.info("=" * 50)

            total_events = len(conversation.state.events)
            logger.info(f"📈 Total events in conversation: {total_events}")

            logger.info("\n🔍 Getting last 5 events using state.events...")
            all_events = conversation.state.events
            recent_events = all_events[-5:] if len(all_events) >= 5 else all_events
            for i, event in enumerate(recent_events, 1):
                event_type = type(event).__name__
                timestamp = getattr(event, "timestamp", "Unknown")
                logger.info(f"  {i}. {event_type} at {timestamp}")

            logger.info("\n🔍 Event types found:")
            event_types = sorted({type(e).__name__ for e in recent_events})
            for et in event_types:
                logger.info(f"  - {et}")
        finally:
            print("\n🧹 Cleaning up conversation...")
            conversation.close()


if __name__ == "__main__":
    main()
