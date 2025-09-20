from __future__ import annotations

import uuid
from datetime import datetime
from typing import Dict, List, Optional

import docker
from docker.errors import APIError, NotFound

from .models import (
    PortBinding,
    RuntimeActionRequest,
    RuntimeActionResponse,
    RuntimeStartRequest,
    RuntimeStartResponse,
)


RUNTIME_LABEL = "openhands.runtime_id"
_docker_client: Optional[docker.DockerClient] = None


class RuntimeNotFoundError(Exception):
    """Raised when a runtime cannot be resolved to a container."""


def _get_client() -> docker.DockerClient:
    global _docker_client
    if _docker_client is None:
        _docker_client = docker.from_env()
    return _docker_client


def _get_container(runtime_id: str) -> docker.models.containers.Container:
    client = _get_client()
    try:
        return client.containers.get(runtime_id)
    except NotFound:
        containers = client.containers.list(
            all=True, filters={"label": f"{RUNTIME_LABEL}={runtime_id}"}
        )
        if not containers:
            raise RuntimeNotFoundError(f"Runtime '{runtime_id}' not found")
        return containers[0]


def _build_ports(
    ports: Optional[List[PortBinding]],
) -> Optional[Dict[str, Optional[int]]]:
    if not ports:
        return None
    bindings: Dict[str, Optional[int]] = {}
    for binding in ports:
        key = binding.docker_key
        if key in bindings:
            raise ValueError(
                f"Duplicate port binding for {binding.container_port}/{binding.protocol}"
            )
        bindings[key] = binding.host_port
    return bindings


def _build_volumes(request: RuntimeStartRequest) -> Optional[Dict[str, Dict[str, str]]]:
    if not request.volumes:
        return None
    volume_dict: Dict[str, Dict[str, str]] = {}
    for volume in request.volumes:
        volume_dict[volume.host_path] = {
            "bind": volume.container_path,
            "mode": volume.mode,
        }
    return volume_dict


def _parse_created(created: str) -> datetime:
    if created.endswith("Z"):
        created = created.replace("Z", "+00:00")
    return datetime.fromisoformat(created)


def start_runtime(request: RuntimeStartRequest) -> RuntimeStartResponse:
    client = _get_client()
    runtime_id = request.name or f"runtime-{uuid.uuid4().hex[:12]}"

    labels = {RUNTIME_LABEL: runtime_id}
    if request.labels:
        labels.update(request.labels)

    try:
        container = client.containers.run(
            image=request.image,
            command=request.command,
            name=runtime_id,
            detach=request.detach,
            environment=request.environment,
            ports=_build_ports(request.ports),
            volumes=_build_volumes(request),
            auto_remove=request.auto_remove,
            labels=labels,
            restart_policy=request.restart_policy,
            network=request.network,
        )
    except APIError as exc:  # pragma: no cover - best effort logging
        raise ValueError(f"Unable to start runtime: {exc.explanation}") from exc

    container.reload()
    attrs = container.attrs
    ports = attrs.get("NetworkSettings", {}).get("Ports", {})

    return RuntimeStartResponse(
        runtime_id=runtime_id,
        container_id=container.id,
        name=container.name,
        image=attrs.get("Config", {}).get("Image", request.image),
        status=container.status,
        created_at=_parse_created(attrs.get("Created", datetime.utcnow().isoformat())),
        ports=ports,
    )


def stop_runtime(request: RuntimeActionRequest) -> RuntimeActionResponse:
    container = _get_container(request.runtime_id)
    try:
        container.stop(timeout=request.timeout)
    except APIError as exc:
        raise ValueError(f"Unable to stop runtime: {exc.explanation}") from exc
    container.reload()
    return RuntimeActionResponse(
        runtime_id=request.runtime_id,
        container_id=container.id,
        status=container.status,
        message=f"Runtime {request.runtime_id} stopped successfully",
    )


def pause_runtime(request: RuntimeActionRequest) -> RuntimeActionResponse:
    container = _get_container(request.runtime_id)
    try:
        container.pause()
    except APIError as exc:
        raise ValueError(f"Unable to pause runtime: {exc.explanation}") from exc
    container.reload()
    return RuntimeActionResponse(
        runtime_id=request.runtime_id,
        container_id=container.id,
        status=container.status,
        message=f"Runtime {request.runtime_id} paused successfully",
    )


def resume_runtime(request: RuntimeActionRequest) -> RuntimeActionResponse:
    container = _get_container(request.runtime_id)
    try:
        container.unpause()
    except APIError as exc:
        raise ValueError(f"Unable to resume runtime: {exc.explanation}") from exc
    container.reload()
    return RuntimeActionResponse(
        runtime_id=request.runtime_id,
        container_id=container.id,
        status=container.status,
        message=f"Runtime {request.runtime_id} resumed successfully",
    )
