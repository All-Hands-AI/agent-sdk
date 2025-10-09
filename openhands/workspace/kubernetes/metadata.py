"""Kubernetes metadata utilities for OpenHands workspace."""

from kubernetes import client as k8s_client  # type: ignore[import-untyped]


def create_metadata(
    workspace_id: str, labels: dict[str, str] | None = None
) -> k8s_client.V1ObjectMeta:
    """Create metadata for Kubernetes resources."""
    final_labels = {"workspace_id": workspace_id}
    if labels:
        final_labels.update(labels)

    return k8s_client.V1ObjectMeta(
        name=f"workspace-{workspace_id}",
        labels=final_labels,
    )
