"""Kubernetes Deployment resource creation."""

from typing import Any

from kubernetes import client as k8s_client  # type: ignore[import-untyped]

from .constants import (
    ADDITIONAL_PVC,
    CPU_LIMIT,
    CPU_REQUEST,
    EPHEMERAL_STORAGE_SIZE,
    INCLUDE_LIVENESS_PROBE,
    INCLUDE_START_PROBE,
    MEMORY_LIMIT,
    MEMORY_REQUEST,
    RUN_AS_GID,
    RUN_AS_UID,
    RUNTIME_CLASS,
    RUNTIME_PODS_PRIVILEGED,
    SANDBOX_API_PORT,
    TERMINATION_GRACE_PERIOD_SECONDS,
    VSCODE_PORT,
    WORK_PORT_1,
    WORK_PORT_2,
)
from .metadata import create_metadata


def _create_pod_security_context(
    security_context: dict[str, Any] | None = None,
) -> k8s_client.V1PodSecurityContext | None:
    """Create pod security context based on passed parameters or environment variables."""  # noqa: E501

    # Determine the security context values to use
    run_as_user = None
    run_as_group = None
    fs_group = None

    if security_context:
        # Use passed parameters if provided
        run_as_user = security_context.get("run_as_user")
        run_as_group = security_context.get("run_as_group")
        fs_group = security_context.get("fs_group")

    # Fall back to environment variables if not provided in security_context
    if run_as_user is None:
        run_as_user = RUN_AS_UID
    if run_as_group is None:
        run_as_group = RUN_AS_GID
    if fs_group is None:
        fs_group = RUN_AS_GID

    # Only create security context if at least one value is set
    if run_as_user is not None or run_as_group is not None or fs_group is not None:
        return k8s_client.V1PodSecurityContext(
            run_as_user=run_as_user,
            run_as_group=run_as_group,
            fs_group=fs_group,
            run_as_non_root=True if run_as_user != 0 else False,
            fs_group_change_policy="Always",
        )

    return None


def create_deployment_manifest(
    workspace_id: str,
    image: str,
    command: list[str] | None = None,
    args: list[str] | None = None,
    environment: dict[str, str] | None = None,
    working_dir: str = "/workspace",
    resource_factor: int = 1,
    runtime_class: str | None = None,
    security_context: dict[str, Any] | None = None,
) -> tuple[k8s_client.V1Deployment, k8s_client.V1Container]:
    """Create a Kubernetes Deployment manifest for a workspace."""

    environment = environment or {}
    command = command or []
    args = args or []

    # Add toleration and node selector for sysbox-runc nodes if needed
    tolerations = []
    node_selector = {}
    pod_annotations = {}
    if runtime_class == "sysbox-runc":
        tolerations.append(
            k8s_client.V1Toleration(
                key="sysbox-runtime",
                operator="Equal",
                value="not-running",
                effect="NoSchedule",
            )
        )
        node_selector["sysbox-install"] = "yes"
        pod_annotations["io.kubernetes.cri-o.userns-mode"] = "auto:size=65536"

    # Set required environment variables
    environment["VSCODE_PORT"] = str(VSCODE_PORT)
    environment["LOG_JSON"] = "1"
    environment["LOG_JSON_LEVEL_KEY"] = "severity"

    # Configure resource requests
    requests = {}
    if CPU_REQUEST:
        cpu_value = int(float(CPU_REQUEST.rstrip("m")))
        requests["cpu"] = f"{int(cpu_value * resource_factor)}m"
    if MEMORY_REQUEST:
        mem_value = int(MEMORY_REQUEST.rstrip("Mi"))
        requests["memory"] = f"{int(mem_value * resource_factor)}Mi"
    if EPHEMERAL_STORAGE_SIZE:
        requests["ephemeral-storage"] = EPHEMERAL_STORAGE_SIZE

    # Configure resource limits
    limits = {}
    if CPU_LIMIT:
        cpu_value = int(float(CPU_LIMIT.rstrip("m")))
        limits["cpu"] = f"{int(cpu_value * resource_factor)}m"
    if MEMORY_LIMIT:
        mem_value = int(MEMORY_LIMIT.rstrip("Mi"))
        mem_value = int(mem_value * resource_factor)
        limits["memory"] = f"{int(mem_value)}Mi"
        # Calculate max memory in GB for runtime
        environment["RUNTIME_MAX_MEMORY_GB"] = str(max(1, mem_value // 1024))
    if EPHEMERAL_STORAGE_SIZE:
        limits["ephemeral-storage"] = EPHEMERAL_STORAGE_SIZE

    # Configure volume mounts
    volume_mounts = [
        k8s_client.V1VolumeMount(name="workspace", mount_path="/workspace")
    ]

    # Handle additional PVC if specified
    additional_volume = None
    if ADDITIONAL_PVC:
        try:
            pvc_name, mount_path = ADDITIONAL_PVC.split(":", 1)
        except ValueError:
            pass  # Invalid format, skip
        else:
            if pvc_name and mount_path:
                volume_mounts.append(
                    k8s_client.V1VolumeMount(
                        name="additional-volume", mount_path=mount_path
                    )
                )
                additional_volume = k8s_client.V1Volume(
                    name="additional-volume",
                    persistent_volume_claim=k8s_client.V1PersistentVolumeClaimVolumeSource(
                        claim_name=pvc_name
                    ),
                )

    # Create container
    container = k8s_client.V1Container(
        name=f"workspace-{workspace_id}",
        image=image,
        image_pull_policy="IfNotPresent",
        command=command if command else None,
        args=args if args else None,
        security_context=k8s_client.V1SecurityContext(
            privileged=RUNTIME_PODS_PRIVILEGED,
        ),
        working_dir=working_dir,
        env=[k8s_client.V1EnvVar(name=k, value=v) for k, v in environment.items()],
        ports=[
            k8s_client.V1ContainerPort(container_port=SANDBOX_API_PORT),
            k8s_client.V1ContainerPort(container_port=VSCODE_PORT),
            k8s_client.V1ContainerPort(container_port=WORK_PORT_1),
            k8s_client.V1ContainerPort(container_port=WORK_PORT_2),
        ],
        resources=k8s_client.V1ResourceRequirements(
            requests=requests,
            limits=limits,
        ),
        volume_mounts=volume_mounts,
    )

    # Add probes if enabled
    if INCLUDE_START_PROBE:
        container.startup_probe = k8s_client.V1Probe(
            http_get=k8s_client.V1HTTPGetAction(
                path="/server_info", port=SANDBOX_API_PORT
            ),
            initial_delay_seconds=5,
            period_seconds=10,
            failure_threshold=30,
        )
    if INCLUDE_LIVENESS_PROBE:
        container.liveness_probe = k8s_client.V1Probe(
            http_get=k8s_client.V1HTTPGetAction(
                path="/server_info", port=SANDBOX_API_PORT
            ),
            timeout_seconds=10,
            period_seconds=30,
            failure_threshold=10,
            success_threshold=1,
        )

    # Create pod metadata
    pod_metadata = create_metadata(workspace_id)
    if pod_annotations:
        pod_metadata.annotations = pod_metadata.annotations or {}
        pod_metadata.annotations.update(pod_annotations)

    # Create deployment
    deployment = k8s_client.V1Deployment(
        metadata=create_metadata(workspace_id),
        spec=k8s_client.V1DeploymentSpec(
            replicas=1,
            selector=k8s_client.V1LabelSelector(
                match_labels={"workspace_id": workspace_id}
            ),
            template=k8s_client.V1PodTemplateSpec(
                metadata=pod_metadata,
                spec=k8s_client.V1PodSpec(
                    enable_service_links=False,
                    termination_grace_period_seconds=TERMINATION_GRACE_PERIOD_SECONDS,
                    security_context=_create_pod_security_context(security_context),
                    containers=[container],
                    volumes=[
                        k8s_client.V1Volume(
                            name="workspace",
                            persistent_volume_claim=k8s_client.V1PersistentVolumeClaimVolumeSource(
                                claim_name=f"workspace-{workspace_id}"
                            ),
                        )
                    ]
                    + ([additional_volume] if additional_volume else []),
                    runtime_class_name=runtime_class
                    if runtime_class is not None
                    else RUNTIME_CLASS,
                    service_account=f"workspace-{workspace_id}",
                    tolerations=tolerations,
                    node_selector=node_selector,
                ),
            ),
        ),
    )

    return deployment, container
