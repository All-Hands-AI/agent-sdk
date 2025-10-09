"""Kubernetes resource creation utilities for OpenHands workspace."""

# pyright: reportOptionalMemberAccess=false

from typing import Any

from kubernetes import client as k8s_client  # type: ignore[import-untyped]


def create_metadata(runtime_id: str, namespace: str = "default") -> Any:
    """Create metadata for Kubernetes resources."""

    return k8s_client.V1ObjectMeta(
        name=f"openhands-workspace-{runtime_id}",
        namespace=namespace,
        labels={"app": "openhands-workspace", "runtime_id": runtime_id},
    )


def create_pvc_manifest(
    runtime_id: str,
    namespace: str = "default",
    storage_size: str = "10Gi",
    storage_class: str | None = None,
) -> Any:
    """Create PersistentVolumeClaim manifest for workspace storage."""

    return k8s_client.V1PersistentVolumeClaim(
        api_version="v1",
        kind="PersistentVolumeClaim",
        metadata=create_metadata(runtime_id, namespace),
        spec=k8s_client.V1PersistentVolumeClaimSpec(
            storage_class_name=storage_class,
            access_modes=["ReadWriteOnce"],
            resources=k8s_client.V1ResourceRequirements(
                requests={"storage": storage_size}
            ),
        ),
    )


def create_service_account_manifest(runtime_id: str, namespace: str = "default") -> Any:
    """Create ServiceAccount manifest for the workspace."""

    return k8s_client.V1ServiceAccount(
        api_version="v1",
        kind="ServiceAccount",
        metadata=create_metadata(runtime_id, namespace),
        automount_service_account_token=False,
    )


def create_deployment_manifest(
    runtime_id: str,
    namespace: str = "default",
    image: str = "ghcr.io/all-hands-ai/agent-server:latest",
    working_dir: str = "/workspace",
    environment: dict[str, str] | None = None,
    cpu_request: str = "100m",
    memory_request: str = "256Mi",
    cpu_limit: str = "1000m",
    memory_limit: str = "1Gi",
    storage_size: str = "1Gi",
) -> Any:
    """Create Deployment manifest for the OpenHands agent server."""

    if environment is None:
        environment = {}

    # Default environment variables
    env_vars = {
        "LOG_JSON": "1",
        "LOG_JSON_LEVEL_KEY": "severity",
        **environment,
    }

    container = k8s_client.V1Container(
        name=f"openhands-workspace-{runtime_id}",
        image=image,
        image_pull_policy="IfNotPresent",
        working_dir=working_dir,
        env=[k8s_client.V1EnvVar(name=k, value=v) for k, v in env_vars.items()],
        ports=[
            k8s_client.V1ContainerPort(container_port=8000, name="api"),
        ],
        resources=k8s_client.V1ResourceRequirements(
            requests={
                "cpu": cpu_request,
                "memory": memory_request,
                "ephemeral-storage": storage_size,
            },
            limits={
                "cpu": cpu_limit,
                "memory": memory_limit,
                "ephemeral-storage": storage_size,
            },
        ),
        volume_mounts=[
            k8s_client.V1VolumeMount(name="workspace", mount_path="/workspace")
        ],
        startup_probe=k8s_client.V1Probe(
            http_get=k8s_client.V1HTTPGetAction(path="/health", port=8000),
            initial_delay_seconds=5,
            period_seconds=10,
            failure_threshold=30,
        ),
        liveness_probe=k8s_client.V1Probe(
            http_get=k8s_client.V1HTTPGetAction(path="/health", port=8000),
            timeout_seconds=10,
            period_seconds=30,
            failure_threshold=10,
            success_threshold=1,
        ),
    )

    return k8s_client.V1Deployment(
        api_version="apps/v1",
        kind="Deployment",
        metadata=create_metadata(runtime_id, namespace),
        spec=k8s_client.V1DeploymentSpec(
            replicas=1,
            selector=k8s_client.V1LabelSelector(
                match_labels={"app": "openhands-workspace", "runtime_id": runtime_id}
            ),
            template=k8s_client.V1PodTemplateSpec(
                metadata=k8s_client.V1ObjectMeta(
                    labels={"app": "openhands-workspace", "runtime_id": runtime_id}
                ),
                spec=k8s_client.V1PodSpec(
                    service_account_name=f"openhands-workspace-{runtime_id}",
                    containers=[container],
                    volumes=[
                        k8s_client.V1Volume(
                            name="workspace",
                            persistent_volume_claim=k8s_client.V1PersistentVolumeClaimVolumeSource(
                                claim_name=f"openhands-workspace-{runtime_id}"
                            ),
                        )
                    ],
                ),
            ),
        ),
    )


def create_service_manifest(runtime_id: str, namespace: str = "default") -> Any:
    """Create Service manifest for the workspace."""

    return k8s_client.V1Service(
        api_version="v1",
        kind="Service",
        metadata=create_metadata(runtime_id, namespace),
        spec=k8s_client.V1ServiceSpec(
            selector={"app": "openhands-workspace", "runtime_id": runtime_id},
            ports=[
                k8s_client.V1ServicePort(
                    name="api",
                    port=8000,
                    target_port=8000,
                ),
            ],
        ),
    )
