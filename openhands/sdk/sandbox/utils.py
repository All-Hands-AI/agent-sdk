"""
Utility functions for sandboxed agent servers.
"""

import subprocess

from openhands.sdk.logger import get_logger

from .docker import build_agent_server_image


logger = get_logger(__name__)


def build_and_push_agent_server_image(
    base_image: str = "nikolaik/python-nodejs:python3.12-nodejs22",
    registry: str = "your-registry.com",
    image_name: str = "agent-server",
    tag: str = "latest",
    target: str = "source",
    variant_name: str | None = None,
    platforms: str = "linux/amd64",
    push: bool = True,
) -> str:
    """
    Build and optionally push an agent server image for use with
    RemoteSandboxedAgentServer.

    This function builds an agent server image locally and optionally pushes it to
    registry where it can be accessed by the remote runtime API.

    Args:
        base_image: Base Docker image to build from
        registry: Docker registry to push to (e.g., "ghcr.io/your-org")
        image_name: Name for the agent server image
        tag: Tag for the image
        target: Build target ("source" or "binary")
        variant_name: Optional variant name for the build
        platforms: Target platforms for the build
        push: Whether to push the image to the registry

    Returns:
        The full image name (registry/image_name:tag)

    Example:
        >>> image = build_and_push_agent_server_image(
        ...     registry="ghcr.io/my-org",
        ...     image_name="my-agent-server",
        ...     tag="v1.0.0"
        ... )
        >>> print(image)  # "ghcr.io/my-org/my-agent-server:v1.0.0"
    """
    logger.info(f"Building agent server image with base: {base_image}")

    # Build the image locally first
    local_image = build_agent_server_image(
        base_image=base_image,
        target=target,
        variant_name=variant_name or "custom",
        platforms=platforms,
    )

    # Create the registry image name
    registry_image = f"{registry.rstrip('/')}/{image_name}:{tag}"

    logger.info(f"Tagging image as: {registry_image}")

    # Tag the image for the registry
    try:
        subprocess.run(
            ["docker", "tag", local_image, registry_image],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to tag image: {e.stderr}") from e

    if push:
        logger.info(f"Pushing image to registry: {registry_image}")
        try:
            subprocess.run(
                ["docker", "push", registry_image],
                check=True,
                capture_output=True,
                text=True,
            )
            logger.info(f"Successfully pushed: {registry_image}")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to push image: {e.stderr}") from e
    else:
        logger.info(f"Skipping push (push=False). Image tagged as: {registry_image}")

    return registry_image


def get_agent_server_build_instructions() -> str:
    """
    Get instructions for building agent server images for RemoteSandboxedAgentServer.

    Returns:
        A string with detailed instructions
    """
    return """
Building Agent Server Images for RemoteSandboxedAgentServer
=========================================================

The RemoteSandboxedAgentServer requires a container image that has the OpenHands
agent server pre-installed. Here are several ways to create such an image:

Method 1: Use the utility function
---------------------------------
from openhands.sdk.sandbox import build_and_push_agent_server_image

image = build_and_push_agent_server_image(
    base_image="nikolaik/python-nodejs:python3.12-nodejs22",
    registry="ghcr.io/your-org",  # Replace with your registry
    image_name="agent-server",
    tag="latest",
    push=True  # Set to False to only build locally
)

Method 2: Build with DockerSandboxedAgentServer and push manually
----------------------------------------------------------------
from openhands.sdk.sandbox import build_agent_server_image
import subprocess

# Build locally
local_image = build_agent_server_image(
    base_image="nikolaik/python-nodejs:python3.12-nodejs22"
)

# Tag for your registry
registry_image = "ghcr.io/your-org/agent-server:latest"
subprocess.run(["docker", "tag", local_image, registry_image], check=True)

# Push to registry
subprocess.run(["docker", "push", registry_image], check=True)

Method 3: Use the agent server Dockerfile directly
--------------------------------------------------
# Clone the OpenHands repository
git clone https://github.com/All-Hands-AI/OpenHands.git
cd OpenHands

# Build using the agent server Dockerfile
docker build -f openhands/agent_server/docker/Dockerfile \\
    --target source \\
    -t your-registry/agent-server:latest .

# Push to registry
docker push your-registry/agent-server:latest

Using the image with RemoteSandboxedAgentServer
----------------------------------------------
with RemoteSandboxedAgentServer(
    api_url="https://runtime-api.example.com",
    api_key="your-api-key",
    base_image="your-registry/agent-server:latest",  # Use your built image
    ...
) as server:
    # Use the server
    pass

Registry Requirements
--------------------
- The registry must be accessible by the remote runtime API
- You may need to authenticate with the registry before pushing
- Common registries: Docker Hub, GitHub Container Registry (ghcr.io),
  Google Container Registry (gcr.io), Amazon ECR, etc.

Authentication Examples
----------------------
# Docker Hub
docker login

# GitHub Container Registry
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin

# Google Container Registry
gcloud auth configure-docker

# Amazon ECR
aws ecr get-login-password --region region | docker login --username AWS \\
    --password-stdin aws_account_id.dkr.ecr.region.amazonaws.com
"""
