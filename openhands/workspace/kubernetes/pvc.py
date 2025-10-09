"""Kubernetes PersistentVolumeClaim resource creation."""

from typing import Any


try:
    from kubernetes import client as k8s_client  # type: ignore[import-untyped]
except ImportError:
    k8s_client = None  # type: ignore[assignment]

from .constants import PERSISTENT_STORAGE_SIZE, STORAGE_CLASS


def _create_metadata(workspace_id: str) -> Any:
    """Create metadata for Kubernetes resources."""
    if k8s_client is None:
        raise ImportError("kubernetes package is required")

    return k8s_client.V1ObjectMeta(
        name=f"workspace-{workspace_id}",
        labels={"workspace_id": workspace_id},
    )


def create_pvc_manifest(workspace_id: str) -> Any:
    """Create a Kubernetes PersistentVolumeClaim manifest for a workspace."""
    if k8s_client is None:
        raise ImportError("kubernetes package is required")

    return k8s_client.V1PersistentVolumeClaim(
        api_version="v1",
        kind="PersistentVolumeClaim",
        metadata=_create_metadata(workspace_id),
        spec=k8s_client.V1PersistentVolumeClaimSpec(
            storage_class_name=STORAGE_CLASS,
            access_modes=["ReadWriteOnce"],
            resources=k8s_client.V1ResourceRequirements(
                requests={"storage": PERSISTENT_STORAGE_SIZE}
            ),
        ),
    )
