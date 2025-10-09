"""Utilities for Kubernetes workspace implementation."""

import random
import string

from .constants import (
    RUNTIME_BASE_URL,
    RUNTIME_URL_SEPARATOR,
    WORK_PORT_1,
    WORK_PORT_2,
    get_scheme,
    is_path_mode,
)


def random_id(length: int = 16) -> str:
    """Generate a random ID string."""
    letters = string.ascii_lowercase
    return "".join(random.choice(letters) for _ in range(length))


def subdomain_to_url(runtime_id: str, hostname_only: bool = False) -> str:
    """Convert runtime ID to URL based on routing mode."""
    if is_path_mode():
        # Host is the shared base; runtime id lives in the path
        if hostname_only:
            return RUNTIME_BASE_URL
        return f"{get_scheme()}://{RUNTIME_BASE_URL}/{runtime_id}/runtime"

    # Default: subdomain-based routing
    hostname = f"{runtime_id}{RUNTIME_URL_SEPARATOR}{RUNTIME_BASE_URL}"
    if hostname_only:
        return hostname
    return f"{get_scheme()}://{hostname}"


def get_work_hosts(runtime_id: str) -> dict[str, int]:
    """Get work host URLs and their corresponding ports."""
    if is_path_mode():
        base = f"{get_scheme()}://{RUNTIME_BASE_URL}"
        work_host_1 = f"{base}/{runtime_id}/work-1"
        work_host_2 = f"{base}/{runtime_id}/work-2"
    else:
        work_host_1 = subdomain_to_url(f"work-1-{runtime_id}", hostname_only=False)
        work_host_2 = subdomain_to_url(f"work-2-{runtime_id}", hostname_only=False)

    return {
        work_host_1: WORK_PORT_1,
        work_host_2: WORK_PORT_2,
    }


def create_workspace_id() -> str:
    """Create a unique workspace ID."""
    return f"ws-{random_id(12)}"


def get_workspace_urls(workspace_id: str) -> dict[str, str]:
    """Get all workspace URLs for different services."""
    base_host = subdomain_to_url(workspace_id, hostname_only=True)

    if is_path_mode():
        base_url = f"{get_scheme()}://{base_host}"
        return {
            "runtime": f"{base_url}/{workspace_id}/runtime",
            "vscode": f"{base_url}/{workspace_id}/vscode",
            "work_1": f"{base_url}/{workspace_id}/work-1",
            "work_2": f"{base_url}/{workspace_id}/work-2",
        }
    else:
        return {
            "runtime": subdomain_to_url(workspace_id),
            "vscode": subdomain_to_url(f"vscode-{workspace_id}"),
            "work_1": subdomain_to_url(f"work-1-{workspace_id}"),
            "work_2": subdomain_to_url(f"work-2-{workspace_id}"),
        }
