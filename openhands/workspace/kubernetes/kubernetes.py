"""Kubernetes-based workspace implementation."""

# pyright: reportOptionalMemberAccess=false

import time
from typing import Any

from kubernetes import (
    client as k8s_client,  # type: ignore[import-untyped]
    config as k8s_config,  # type: ignore[import-untyped]
)
from kubernetes.client.rest import ApiException  # type: ignore[import-untyped]
from pydantic import Field, PrivateAttr

from openhands.sdk.logger import get_logger
from openhands.sdk.workspace import RemoteWorkspace

from .constants import K8S_NAMESPACE
from .deployment import create_deployment_manifest
from .ingress import create_ingress_manifest
from .pvc import create_pvc_manifest
from .service import create_service_manifest
from .service_account import create_service_account_manifest
from .utils import create_workspace_id, get_workspace_urls


logger = get_logger(__name__)


class KubernetesWorkspace(RemoteWorkspace):
    """Kubernetes-based workspace that creates and manages Kubernetes resources.

    This workspace creates a Kubernetes deployment running the OpenHands agent server,
    exposes it via ingress, and provides remote workspace operations through the
    ingress URL.

    Example:
        with KubernetesWorkspace(
            image="ghcr.io/all-hands-ai/agent-server:latest",
            namespace="openhands"
        ) as workspace:
            result = workspace.execute_command("ls -la")
    """

    # Override parent fields with defaults
    working_dir: str = Field(
        default="/workspace",
        description="Working directory inside the container.",
    )
    host: str = Field(
        default="",
        description="Remote host URL (set automatically from ingress).",
    )

    # Kubernetes-specific configuration
    image: str = Field(
        default="ghcr.io/all-hands-ai/agent-server:latest",
        description="Container image to use for the agent server pod.",
    )
    namespace: str = Field(
        default=K8S_NAMESPACE,
        description="Kubernetes namespace to create resources in.",
    )
    environment: dict[str, str] = Field(
        default_factory=dict,
        description="Environment variables to set in the container.",
    )
    cleanup_on_exit: bool = Field(
        default=True,
        description="Whether to clean up Kubernetes resources on exit.",
    )
    resource_factor: int = Field(
        default=1,
        description="Resource scaling factor for CPU and memory.",
    )
    runtime_class: str | None = Field(
        default=None,
        description="Kubernetes runtime class to use.",
    )
    security_context: dict[str, Any] | None = Field(
        default=None,
        description="Security context configuration.",
    )

    _workspace_id: str = PrivateAttr()
    _k8s_core_api: Any = PrivateAttr()
    _k8s_apps_api: Any = PrivateAttr()
    _k8s_networking_api: Any = PrivateAttr()
    _workspace_urls: dict[str, str] = PrivateAttr()

    def model_post_init(self, context: Any) -> None:
        """Set up the Kubernetes resources and initialize the remote workspace."""
        # Generate unique workspace ID
        self._workspace_id = create_workspace_id()

        # Load Kubernetes configuration
        try:
            # Try in-cluster config first
            k8s_config.load_incluster_config()
            logger.info("Loaded in-cluster Kubernetes configuration")
        except k8s_config.ConfigException:
            try:
                # Fall back to local kubeconfig
                k8s_config.load_kube_config()
                logger.info("Loaded local Kubernetes configuration")
            except k8s_config.ConfigException as e:
                raise RuntimeError(
                    "Could not load Kubernetes configuration. "
                    "Make sure you have a valid kubeconfig or are running in a cluster."
                ) from e

        # Initialize Kubernetes API clients
        self._k8s_core_api = k8s_client.CoreV1Api()
        self._k8s_apps_api = k8s_client.AppsV1Api()
        self._k8s_networking_api = k8s_client.NetworkingV1Api()

        # Get workspace URLs
        self._workspace_urls = get_workspace_urls(self._workspace_id)

        # Create Kubernetes resources
        self._create_kubernetes_resources()

        # Wait for deployment to be ready
        self._wait_for_deployment_ready()

        # Set host for RemoteWorkspace to use
        object.__setattr__(self, "host", self._workspace_urls["runtime"])
        object.__setattr__(self, "api_key", None)

        # Wait for the service to be healthy
        self._wait_for_health()
        logger.info("Kubernetes workspace is ready at %s", self.host)

        # Now initialize the parent RemoteWorkspace
        super().model_post_init(context)

    def _create_kubernetes_resources(self) -> None:
        """Create all necessary Kubernetes resources."""
        logger.info(
            f"Creating Kubernetes resources for workspace: {self._workspace_id}"
        )

        try:
            # Create ServiceAccount
            sa_manifest = create_service_account_manifest(self._workspace_id)
            self._k8s_core_api.create_namespaced_service_account(
                namespace=self.namespace, body=sa_manifest
            )
            logger.debug("ServiceAccount created")

            # Create PersistentVolumeClaim
            pvc_manifest = create_pvc_manifest(self._workspace_id)
            self._k8s_core_api.create_namespaced_persistent_volume_claim(
                namespace=self.namespace, body=pvc_manifest
            )
            logger.debug("PersistentVolumeClaim created")

            # Create Deployment
            deployment_manifest, _ = create_deployment_manifest(
                workspace_id=self._workspace_id,
                image=self.image,
                environment=self.environment,
                working_dir=self.working_dir,
                resource_factor=self.resource_factor,
                runtime_class=self.runtime_class,
                security_context=self.security_context,
            )
            deployment = self._k8s_apps_api.create_namespaced_deployment(
                namespace=self.namespace, body=deployment_manifest
            )
            logger.debug("Deployment created")

            # Create Service
            service_manifest = create_service_manifest(self._workspace_id)
            # Set owner reference to deployment for cleanup
            owner_reference = k8s_client.V1OwnerReference(
                api_version="apps/v1",
                kind="Deployment",
                name=deployment.metadata.name,
                uid=deployment.metadata.uid,
            )
            service_manifest.metadata.owner_references = [owner_reference]

            self._k8s_core_api.create_namespaced_service(
                namespace=self.namespace, body=service_manifest
            )
            logger.debug("Service created")

            # Create Ingress
            ingress_manifest = create_ingress_manifest(self._workspace_id)
            # Set owner reference to deployment for cleanup
            ingress_manifest.metadata.owner_references = [owner_reference]

            self._k8s_networking_api.create_namespaced_ingress(
                namespace=self.namespace, body=ingress_manifest
            )
            logger.debug("Ingress created")

            logger.info("All Kubernetes resources created successfully")

        except ApiException as e:
            logger.error(f"Failed to create Kubernetes resources: {e}")
            self._cleanup_resources()
            raise RuntimeError(f"Failed to create Kubernetes resources: {e}") from e

    def _wait_for_deployment_ready(self, timeout: float = 300.0) -> None:
        """Wait for the deployment to be ready."""
        logger.info("Waiting for deployment to be ready...")
        start_time = time.time()
        deployment_name = f"workspace-{self._workspace_id}"

        while time.time() - start_time < timeout:
            try:
                deployment = self._k8s_apps_api.read_namespaced_deployment(
                    name=deployment_name, namespace=self.namespace
                )

                if (
                    deployment.status.ready_replicas
                    and deployment.status.ready_replicas >= 1
                ):
                    logger.info("Deployment is ready")
                    return

            except ApiException as e:
                logger.warning(f"Error checking deployment status: {e}")

            time.sleep(2)

        raise RuntimeError(
            f"Deployment failed to become ready within {timeout} seconds"
        )

    def _wait_for_health(self, timeout: float = 120.0) -> None:
        """Wait for the service to become healthy."""
        import urllib.error
        import urllib.request

        start = time.time()
        health_url = f"{self.host}/health"

        while time.time() - start < timeout:
            try:
                with urllib.request.urlopen(health_url, timeout=5.0) as resp:
                    if 200 <= resp.status < 300:
                        return
            except (urllib.error.URLError, OSError):
                pass

            time.sleep(2)

        raise RuntimeError("Service failed to become healthy in time")

    def _cleanup_resources(self) -> None:
        """Clean up all Kubernetes resources."""
        if not self.cleanup_on_exit:
            logger.info("Cleanup disabled, leaving Kubernetes resources")
            return

        logger.info(
            f"Cleaning up Kubernetes resources for workspace: {self._workspace_id}"
        )

        deployment_name = f"workspace-{self._workspace_id}"

        # Delete deployment (this will also delete pods due to owner references)
        try:
            self._k8s_apps_api.delete_namespaced_deployment(
                name=deployment_name, namespace=self.namespace
            )
            logger.debug("Deployment deleted")
        except Exception as e:
            # Check if it's a 404 error (resource not found) which is expected
            if hasattr(e, "status") and getattr(e, "status", None) == 404:
                pass  # Resource already deleted, which is fine
            else:
                logger.warning(f"Failed to delete deployment: {e}")

        # Other resources (Service, Ingress, PVC, ServiceAccount) will be cleaned up
        # automatically due to owner references

    @property
    def workspace_urls(self) -> dict[str, str]:
        """Get all workspace URLs for different services."""
        return self._workspace_urls.copy()

    @property
    def workspace_id(self) -> str:
        """Get the workspace ID."""
        return self._workspace_id

    def __enter__(self) -> "KubernetesWorkspace":
        """Context manager entry - returns the workspace itself."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore[no-untyped-def]
        """Context manager exit - cleans up the Kubernetes resources."""
        self.cleanup()

    def __del__(self) -> None:
        """Clean up the Kubernetes resources when the workspace is destroyed."""
        self.cleanup()

    def cleanup(self) -> None:
        """Clean up all Kubernetes resources."""
        self._cleanup_resources()
