"""Constants for Kubernetes workspace implementation."""

import os
from pathlib import Path
from typing import Any


try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

# Port configurations
SANDBOX_API_PORT = 60000
VSCODE_PORT = 60001
WORK_PORT_1 = 12000
WORK_PORT_2 = 12001

# Kubernetes configuration
K8S_NAMESPACE = os.environ.get("K8S_NAMESPACE", "openhands-workspaces")
STORAGE_CLASS = os.environ.get("STORAGE_CLASS", "standard")
PERSISTENT_STORAGE_SIZE = os.environ.get("PERSISTENT_STORAGE_SIZE", "10Gi")
EPHEMERAL_STORAGE_SIZE = os.environ.get("EPHEMERAL_STORAGE_SIZE", "10Gi")

# Resource limits
MEMORY_REQUEST = os.environ.get("MEMORY_REQUEST", "2048Mi")
MEMORY_LIMIT = os.environ.get("MEMORY_LIMIT", "4096Mi")
CPU_REQUEST = os.environ.get("CPU_REQUEST", "1000m")
CPU_LIMIT = os.environ.get("CPU_LIMIT", "2000m")

# Security context
RUN_AS_UID = int(os.environ.get("RUN_AS_UID", "1000"))
RUN_AS_GID = int(os.environ.get("RUN_AS_GID", "1000"))

# Runtime configuration
RUNTIME_CLASS = os.environ.get("RUNTIME_CLASS") or None
RUNTIME_PODS_PRIVILEGED = (
    os.environ.get("RUNTIME_PODS_PRIVILEGED", "false").lower() == "true"
)
TERMINATION_GRACE_PERIOD_SECONDS = int(
    os.environ.get("TERMINATION_GRACE_PERIOD_SECONDS", "30")
)
REQUEST_MAX_DURATION_SECONDS = int(
    os.environ.get("REQUEST_MAX_DURATION_SECONDS", "300")
)

# Ingress configuration
INGRESS_CLASS = os.environ.get("INGRESS_CLASS", "traefik")
INGRESS_BASE = os.environ.get("INGRESS_BASE")
RUNTIME_BASE_URL = os.environ.get("RUNTIME_BASE_URL", "workspace.localhost")
RUNTIME_DISABLE_SSL = os.environ.get("RUNTIME_DISABLE_SSL", "true").lower() == "true"
RUNTIME_ROUTING_MODE = os.environ.get("RUNTIME_ROUTING_MODE", "subdomain").lower()
RUNTIME_URL_SEPARATOR = os.environ.get("RUNTIME_URL_SEPARATOR", ".")
RUNTIME_CERT_SECRET = os.environ.get("RUNTIME_CERT_SECRET", "")

# Gateway API configuration
USE_GATEWAY_API = os.environ.get("USE_GATEWAY_API", "false").lower() == "true"

# Load base ingress from file if INGRESS_BASE is set
BASE_INGRESS_DATA: dict[str, Any] | None = None
if INGRESS_BASE and yaml:
    base_ingress_path = Path(INGRESS_BASE)
    if base_ingress_path.exists():
        try:
            with open(base_ingress_path) as f:
                BASE_INGRESS_DATA = yaml.safe_load(f)

            # Validate that it's an ingress resource
            if not BASE_INGRESS_DATA or BASE_INGRESS_DATA.get("kind") != "Ingress":
                BASE_INGRESS_DATA = None
        except Exception:
            BASE_INGRESS_DATA = None

# Additional PVC configuration
ADDITIONAL_PVC = os.environ.get("ADDITIONAL_PVC")

# Probe configuration
INCLUDE_LIVENESS_PROBE = (
    os.environ.get("INCLUDE_LIVENESS_PROBE", "true").lower() == "true"
)
INCLUDE_START_PROBE = os.environ.get("INCLUDE_START_PROBE", "true").lower() == "true"


def is_path_mode() -> bool:
    """Check if path-based routing is enabled."""
    return (
        USE_GATEWAY_API
        or RUNTIME_ROUTING_MODE == "path"
        or RUNTIME_URL_SEPARATOR == "/"
    )


def get_scheme() -> str:
    """Get the URL scheme (http or https)."""
    return "http" if RUNTIME_DISABLE_SSL else "https"
