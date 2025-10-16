"""Kubernetes PersistentVolumeClaim resource creation."""

from kubernetes import client as k8s_client  # type: ignore[import-untyped]

from .constants import PERSISTENT_STORAGE_SIZE, STORAGE_CLASS
from .metadata import create_metadata


def create_pvc_manifest(workspace_id: str) -> k8s_client.V1PersistentVolumeClaim:
    """Create a Kubernetes PersistentVolumeClaim manifest for a workspace."""
    return k8s_client.V1PersistentVolumeClaim(
        api_version="v1",
        kind="PersistentVolumeClaim",
        metadata=create_metadata(workspace_id),
        spec=k8s_client.V1PersistentVolumeClaimSpec(
            storage_class_name=STORAGE_CLASS,
            access_modes=["ReadWriteOnce"],
            resources=k8s_client.V1ResourceRequirements(
                requests={"storage": PERSISTENT_STORAGE_SIZE}
            ),
        ),
    )
