"""Kubernetes Ingress resource creation."""

import os

from kubernetes import client as k8s_client  # type: ignore[import-untyped]

from .constants import (
    BASE_INGRESS_DATA,
    INGRESS_CLASS,
    REQUEST_MAX_DURATION_SECONDS,
    RUNTIME_CERT_SECRET,
    SANDBOX_API_PORT,
    VSCODE_PORT,
    WORK_PORT_1,
    WORK_PORT_2,
    is_path_mode,
)
from .metadata import create_metadata
from .utils import subdomain_to_url


def create_ingress_manifest(workspace_id: str) -> k8s_client.V1Ingress:
    """Create a Kubernetes Ingress manifest for a workspace."""
    base_host = subdomain_to_url(workspace_id, hostname_only=True)
    vscode_host = subdomain_to_url(f"vscode-{workspace_id}", hostname_only=True)
    work_port_1_host = subdomain_to_url(f"work-1-{workspace_id}", hostname_only=True)
    work_port_2_host = subdomain_to_url(f"work-2-{workspace_id}", hostname_only=True)
    metadata = create_metadata(workspace_id)

    # Start with default annotations
    annotations = {
        "traefik.ingress.kubernetes.io/response-forwarding-timeout": str(
            REQUEST_MAX_DURATION_SECONDS
        ),
    }

    # Determine ingress class and inherit from base ingress if specified
    ingress_class = INGRESS_CLASS
    base_labels = {}
    base_annotations = {}

    if BASE_INGRESS_DATA:
        # Extract metadata from loaded base ingress data
        base_metadata = BASE_INGRESS_DATA.get("metadata", {})

        # Inherit labels from base ingress (excluding workspace-specific ones)
        if base_metadata.get("labels"):
            base_labels = {
                k: v
                for k, v in base_metadata["labels"].items()
                if k not in ["workspace_id"]
            }

        # Inherit annotations from base ingress
        if base_metadata.get("annotations"):
            base_annotations = dict(base_metadata["annotations"])

        # If INGRESS_CLASS is not explicitly set in environment, inherit from base
        if (
            not os.environ.get("INGRESS_CLASS")
            and "kubernetes.io/ingress.class" in base_annotations
        ):
            ingress_class = base_annotations["kubernetes.io/ingress.class"]

    # Merge annotations: base annotations first, then our defaults, then ingress class
    final_annotations = {}
    final_annotations.update(base_annotations)
    final_annotations.update(annotations)
    final_annotations["kubernetes.io/ingress.class"] = ingress_class

    # Merge labels: base labels first, then our workspace-specific labels
    final_labels = {}
    final_labels.update(base_labels)
    if metadata.labels:
        final_labels.update(metadata.labels)

    metadata.annotations = final_annotations
    metadata.labels = final_labels

    if is_path_mode():
        # Support path-based ingress when using nginx ingress controller
        if ingress_class not in ("nginx", "ingress-nginx"):
            raise TypeError(
                "create_ingress_manifest failed because path mode is only "
                "supported with ingress-nginx"
            )

        # Ensure required annotations for nginx path-based routing
        metadata.annotations = metadata.annotations or {}
        metadata.annotations.setdefault(
            "external-dns.alpha.kubernetes.io/hostname", base_host
        )
        metadata.annotations.setdefault(
            "nginx.ingress.kubernetes.io/rewrite-target", "/$2"
        )

        tls = []
        if RUNTIME_CERT_SECRET:
            tls = [
                k8s_client.V1IngressTLS(
                    hosts=[base_host],
                    secret_name=RUNTIME_CERT_SECRET,
                )
            ]

        return k8s_client.V1Ingress(
            metadata=metadata,
            spec=k8s_client.V1IngressSpec(
                tls=tls,
                rules=[
                    k8s_client.V1IngressRule(
                        host=base_host,
                        http=k8s_client.V1HTTPIngressRuleValue(
                            paths=[
                                k8s_client.V1HTTPIngressPath(
                                    path=f"/{workspace_id}/runtime(/|$)(.*)",
                                    path_type="ImplementationSpecific",
                                    backend=k8s_client.V1IngressBackend(
                                        service=k8s_client.V1IngressServiceBackend(
                                            name=f"workspace-{workspace_id}",
                                            port=k8s_client.V1ServiceBackendPort(
                                                number=SANDBOX_API_PORT
                                            ),
                                        )
                                    ),
                                ),
                                k8s_client.V1HTTPIngressPath(
                                    path=f"/{workspace_id}/vscode(/|$)(.*)",
                                    path_type="ImplementationSpecific",
                                    backend=k8s_client.V1IngressBackend(
                                        service=k8s_client.V1IngressServiceBackend(
                                            name=f"workspace-{workspace_id}",
                                            port=k8s_client.V1ServiceBackendPort(
                                                number=VSCODE_PORT
                                            ),
                                        )
                                    ),
                                ),
                                k8s_client.V1HTTPIngressPath(
                                    path=f"/{workspace_id}/work-1(/|$)(.*)",
                                    path_type="ImplementationSpecific",
                                    backend=k8s_client.V1IngressBackend(
                                        service=k8s_client.V1IngressServiceBackend(
                                            name=f"workspace-{workspace_id}",
                                            port=k8s_client.V1ServiceBackendPort(
                                                number=WORK_PORT_1
                                            ),
                                        )
                                    ),
                                ),
                                k8s_client.V1HTTPIngressPath(
                                    path=f"/{workspace_id}/work-2(/|$)(.*)",
                                    path_type="ImplementationSpecific",
                                    backend=k8s_client.V1IngressBackend(
                                        service=k8s_client.V1IngressServiceBackend(
                                            name=f"workspace-{workspace_id}",
                                            port=k8s_client.V1ServiceBackendPort(
                                                number=WORK_PORT_2
                                            ),
                                        )
                                    ),
                                ),
                            ]
                        ),
                    )
                ],
            ),
        )

    # Subdomain-based routing (default)
    return k8s_client.V1Ingress(
        metadata=metadata,
        spec=k8s_client.V1IngressSpec(
            rules=[
                k8s_client.V1IngressRule(
                    host=base_host,
                    http=k8s_client.V1HTTPIngressRuleValue(
                        paths=[
                            k8s_client.V1HTTPIngressPath(
                                path="/",
                                path_type="Prefix",
                                backend=k8s_client.V1IngressBackend(
                                    service=k8s_client.V1IngressServiceBackend(
                                        name=f"workspace-{workspace_id}",
                                        port=k8s_client.V1ServiceBackendPort(
                                            number=SANDBOX_API_PORT
                                        ),
                                    )
                                ),
                            )
                        ]
                    ),
                ),
                k8s_client.V1IngressRule(
                    host=vscode_host,
                    http=k8s_client.V1HTTPIngressRuleValue(
                        paths=[
                            k8s_client.V1HTTPIngressPath(
                                path="/",
                                path_type="Prefix",
                                backend=k8s_client.V1IngressBackend(
                                    service=k8s_client.V1IngressServiceBackend(
                                        name=f"workspace-{workspace_id}",
                                        port=k8s_client.V1ServiceBackendPort(
                                            number=VSCODE_PORT
                                        ),
                                    )
                                ),
                            )
                        ]
                    ),
                ),
                k8s_client.V1IngressRule(
                    host=work_port_1_host,
                    http=k8s_client.V1HTTPIngressRuleValue(
                        paths=[
                            k8s_client.V1HTTPIngressPath(
                                path="/",
                                path_type="Prefix",
                                backend=k8s_client.V1IngressBackend(
                                    service=k8s_client.V1IngressServiceBackend(
                                        name=f"workspace-{workspace_id}",
                                        port=k8s_client.V1ServiceBackendPort(
                                            number=WORK_PORT_1
                                        ),
                                    )
                                ),
                            )
                        ]
                    ),
                ),
                k8s_client.V1IngressRule(
                    host=work_port_2_host,
                    http=k8s_client.V1HTTPIngressRuleValue(
                        paths=[
                            k8s_client.V1HTTPIngressPath(
                                path="/",
                                path_type="Prefix",
                                backend=k8s_client.V1IngressBackend(
                                    service=k8s_client.V1IngressServiceBackend(
                                        name=f"workspace-{workspace_id}",
                                        port=k8s_client.V1ServiceBackendPort(
                                            number=WORK_PORT_2
                                        ),
                                    )
                                ),
                            )
                        ]
                    ),
                ),
            ],
            tls=[
                k8s_client.V1IngressTLS(
                    hosts=[
                        base_host,
                        vscode_host,
                        work_port_1_host,
                        work_port_2_host,
                    ],
                    secret_name=RUNTIME_CERT_SECRET,
                )
            ]
            if RUNTIME_CERT_SECRET
            else [],
        ),
    )
