"""Kubernetes ServiceAccount resource creation."""

from kubernetes import client as k8s_client  # type: ignore[import-untyped]

from .metadata import create_metadata


def create_service_account_manifest(workspace_id: str) -> k8s_client.V1ServiceAccount:
    """Create a Kubernetes ServiceAccount manifest for a workspace."""
    return k8s_client.V1ServiceAccount(
        api_version="v1",
        kind="ServiceAccount",
        metadata=create_metadata(workspace_id),
        automount_service_account_token=False,
    )
