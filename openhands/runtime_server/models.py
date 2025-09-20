from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, model_validator


class PortBinding(BaseModel):
    container_port: int = Field(..., ge=1, le=65535)
    host_port: Optional[int] = Field(None, ge=1, le=65535)
    protocol: Literal["tcp", "udp"] = "tcp"

    @property
    def docker_key(self) -> str:
        return f"{self.container_port}/{self.protocol}"


class VolumeMount(BaseModel):
    host_path: str = Field(..., min_length=1)
    container_path: str = Field(..., min_length=1)
    mode: Literal["rw", "ro"] = "rw"


class RuntimeStartRequest(BaseModel):
    image: str = Field(..., min_length=1, description="Docker image to run")
    name: Optional[str] = Field(
        None, min_length=1, description="Optional explicit name for the runtime"
    )
    command: Optional[Union[str, List[str]]] = Field(
        None, description="Command (string or list) to execute in the container"
    )
    environment: Optional[Dict[str, str]] = Field(
        default=None, description="Environment variables to set inside the container"
    )
    ports: Optional[List[PortBinding]] = Field(
        default=None, description="Container to host port bindings"
    )
    volumes: Optional[List[VolumeMount]] = Field(
        default=None, description="Volume mounts from host to container"
    )
    detach: bool = Field(
        default=True,
        description="Run the container in detached mode. This should generally be true",
    )
    auto_remove: bool = Field(
        default=False,
        description="Remove the container automatically when it exits",
    )
    labels: Optional[Dict[str, str]] = Field(
        default=None, description="Additional Docker labels to apply"
    )
    restart_policy: Optional[Dict[str, str]] = Field(
        default=None,
        description='Optional Docker restart policy (e.g. {"Name": "on-failure"})',
    )
    network: Optional[str] = Field(
        default=None, description="Optional Docker network to attach the container to"
    )

    @model_validator(mode="after")
    def validate_detach(cls, value: "RuntimeStartRequest") -> "RuntimeStartRequest":
        if not value.detach:
            raise ValueError("detach must be true to avoid blocking the API call")
        return value


class RuntimeStartResponse(BaseModel):
    runtime_id: str
    container_id: str
    name: str
    image: str
    status: str
    created_at: datetime
    ports: Dict[str, List[Dict[str, Optional[str]]]]


class RuntimeActionRequest(BaseModel):
    runtime_id: str = Field(..., min_length=1, description="Runtime identifier")
    timeout: Optional[int] = Field(
        default=None,
        ge=0,
        description="Seconds to wait before forcing the stop action (stop only)",
    )


class RuntimeActionResponse(BaseModel):
    runtime_id: str
    container_id: str
    status: str
    message: str
