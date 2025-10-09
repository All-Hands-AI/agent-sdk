"""Tests for KubernetesWorkspace."""

from unittest.mock import MagicMock, patch

from kubernetes import config as k8s_config  # type: ignore[import-untyped]

from openhands.workspace.kubernetes import KubernetesWorkspace


def test_kubernetes_workspace_import():
    """Test that KubernetesWorkspace can be imported."""
    assert KubernetesWorkspace is not None


@patch("openhands.workspace.kubernetes.kubernetes.KubernetesWorkspace._wait_for_health")
@patch(
    "openhands.workspace.kubernetes.kubernetes.KubernetesWorkspace._wait_for_deployment_ready"
)
@patch("openhands.workspace.kubernetes.kubernetes.k8s_client.AppsV1Api")
@patch("openhands.workspace.kubernetes.kubernetes.k8s_client.CoreV1Api")
@patch("openhands.workspace.kubernetes.kubernetes.k8s_client.NetworkingV1Api")
@patch("openhands.workspace.kubernetes.kubernetes.k8s_config.load_incluster_config")
@patch("openhands.workspace.kubernetes.kubernetes.k8s_config.load_kube_config")
def test_kubernetes_workspace_init(
    mock_load_kube_config,
    mock_load_incluster_config,
    mock_networking_api,
    mock_core_api,
    mock_apps_api,
    mock_wait_for_deployment,
    mock_wait_for_health,
):
    """Test KubernetesWorkspace initialization."""
    # Mock the kubernetes config loading to fail for incluster, succeed for kube_config
    mock_load_incluster_config.side_effect = k8s_config.ConfigException(
        "Not in cluster"
    )
    mock_load_kube_config.return_value = None

    # Mock the API clients
    mock_apps_api_instance = MagicMock()
    mock_core_api_instance = MagicMock()
    mock_networking_api_instance = MagicMock()

    mock_apps_api.return_value = mock_apps_api_instance
    mock_core_api.return_value = mock_core_api_instance
    mock_networking_api.return_value = mock_networking_api_instance

    # Mock deployment status for readiness check
    mock_deployment = MagicMock()
    mock_deployment.status.ready_replicas = 1
    mock_apps_api_instance.read_namespaced_deployment.return_value = mock_deployment

    # Mock the wait methods to return immediately
    mock_wait_for_deployment.return_value = None
    mock_wait_for_health.return_value = None

    workspace = KubernetesWorkspace(
        image="test-image:latest", namespace="test-namespace"
    )

    assert workspace.image == "test-image:latest"
    assert workspace.namespace == "test-namespace"
    assert workspace.workspace_id is not None
    assert workspace.host is not None


@patch("openhands.workspace.kubernetes.kubernetes.KubernetesWorkspace._wait_for_health")
@patch(
    "openhands.workspace.kubernetes.kubernetes.KubernetesWorkspace._wait_for_deployment_ready"
)
@patch("openhands.workspace.kubernetes.kubernetes.k8s_client.AppsV1Api")
@patch("openhands.workspace.kubernetes.kubernetes.k8s_client.CoreV1Api")
@patch("openhands.workspace.kubernetes.kubernetes.k8s_client.NetworkingV1Api")
@patch("openhands.workspace.kubernetes.kubernetes.k8s_config.load_incluster_config")
@patch("openhands.workspace.kubernetes.kubernetes.k8s_config.load_kube_config")
def test_kubernetes_workspace_properties(
    mock_load_kube_config,
    mock_load_incluster_config,
    mock_networking_api,
    mock_core_api,
    mock_apps_api,
    mock_wait_for_deployment,
    mock_wait_for_health,
):
    """Test KubernetesWorkspace properties."""
    # Mock the kubernetes config loading
    mock_load_incluster_config.side_effect = k8s_config.ConfigException(
        "Not in cluster"
    )
    mock_load_kube_config.return_value = None

    # Mock the API clients
    mock_apps_api_instance = MagicMock()
    mock_core_api_instance = MagicMock()
    mock_networking_api_instance = MagicMock()

    mock_apps_api.return_value = mock_apps_api_instance
    mock_core_api.return_value = mock_core_api_instance
    mock_networking_api.return_value = mock_networking_api_instance

    # Mock deployment status for readiness check
    mock_deployment = MagicMock()
    mock_deployment.status.ready_replicas = 1
    mock_apps_api_instance.read_namespaced_deployment.return_value = mock_deployment

    # Mock the wait methods to return immediately
    mock_wait_for_deployment.return_value = None
    mock_wait_for_health.return_value = None

    workspace = KubernetesWorkspace(
        image="test-image:latest", namespace="test-namespace"
    )

    # Test that workspace_id is generated
    assert workspace.workspace_id.startswith("ws-")

    # Test that host is set based on workspace_id
    assert workspace.host is not None
    assert workspace.workspace_id in workspace.host
