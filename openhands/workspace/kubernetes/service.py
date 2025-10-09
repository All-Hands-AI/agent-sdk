"""Kubernetes Service resource creation."""

from kubernetes import client as k8s_client  # type: ignore[import-untyped]

from .constants import SANDBOX_API_PORT, VSCODE_PORT, WORK_PORT_1, WORK_PORT_2
from .metadata import create_metadata


def create_service_manifest(workspace_id: str) -> k8s_client.V1Service:
    """Create a Kubernetes Service manifest for a workspace."""
    return k8s_client.V1Service(
        metadata=create_metadata(workspace_id),
        spec=k8s_client.V1ServiceSpec(
            selector={"workspace_id": workspace_id},
            ports=[
                k8s_client.V1ServicePort(
                    name="action-execution-api",
                    port=SANDBOX_API_PORT,
                    target_port=SANDBOX_API_PORT,
                ),
                k8s_client.V1ServicePort(
                    name="vscode",
                    port=VSCODE_PORT,
                    target_port=VSCODE_PORT,
                ),
                k8s_client.V1ServicePort(
                    name="work-port-1",
                    port=WORK_PORT_1,
                    target_port=WORK_PORT_1,
                ),
                k8s_client.V1ServicePort(
                    name="work-port-2",
                    port=WORK_PORT_2,
                    target_port=WORK_PORT_2,
                ),
            ],
        ),
    )
