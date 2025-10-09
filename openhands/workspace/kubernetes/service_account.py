"""Kubernetes ServiceAccount resource creation."""

from typing import Any


try:
    from kubernetes import client as k8s_client  # type: ignore[import-untyped]
except ImportError:
    k8s_client = None  # type: ignore[assignment]


def _create_metadata(workspace_id: str) -> Any:
    """Create metadata for Kubernetes resources."""
    if k8s_client is None:
        raise ImportError("kubernetes package is required")

    return k8s_client.V1ObjectMeta(
        name=f"workspace-{workspace_id}",
        labels={"workspace_id": workspace_id},
    )


def create_service_account_manifest(workspace_id: str) -> Any:
    """Create a Kubernetes ServiceAccount manifest for a workspace."""
    if k8s_client is None:
        raise ImportError("kubernetes package is required")

    return k8s_client.V1ServiceAccount(
        api_version="v1",
        kind="ServiceAccount",
        metadata=_create_metadata(workspace_id),
        automount_service_account_token=False,
    )
