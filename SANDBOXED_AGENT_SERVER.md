# Sandboxed Agent Server

This document describes the sandboxed agent server implementations available in the OpenHands SDK.

## Overview

The sandboxed agent server allows you to run the OpenHands Agent Server in isolated environments for development, testing, and production use. There are two main implementations:

1. **DockerSandboxedAgentServer** - Runs the agent server in a local Docker container
2. **RemoteSandboxedAgentServer** - Runs the agent server using a remote runtime API

## Abstract Base Class

All sandboxed agent server implementations inherit from `SandboxedAgentServer`, which provides a common interface:

```python
from openhands.sdk.sandbox import SandboxedAgentServer

# Use as a context manager
with SomeConcreteServer(host_port=8010) as server:
    # server.base_url contains the URL to connect to
    conversation = Conversation(agent=agent, host=server.base_url)
    ...
```

### Bash Execution and File Operations

All sandboxed agent server implementations provide methods for executing bash commands and managing files in the sandboxed environment:

#### Bash Execution

```python
# Execute a bash command
result = server.execute_bash("echo 'Hello World!'")
print(f"Command ID: {result.command_id}")
print(f"Command: {result.command}")
print(f"Is running: {result.is_running}")

# Execute with custom working directory and timeout
result = server.execute_bash(
    "ls -la", 
    cwd="/tmp", 
    timeout=60
)
```

The `execute_bash` method returns a `BashExecutionResult` object with:
- `command_id`: Unique identifier for the command execution
- `command`: The executed command string
- `exit_code`: Exit code (None if still running)
- `output`: Command output (initially empty, populated as command runs)
- `is_running`: Boolean indicating if the command is still executing

#### File Upload Operations

```python
# Upload a file from local filesystem
success = server.upload_file("/path/to/local/file.txt", "remote_file.txt")

# Upload file content directly
content = "Hello from the host!\nThis is file content."
success = server.upload_file_content(content, "created_file.txt")

# Upload binary content
binary_content = b"\x89PNG\r\n\x1a\n..."  # Binary data
success = server.upload_file_content(binary_content, "image.png")
```

#### File Download Operations

```python
# Download file as bytes
content = server.download_file("remote_file.txt")
if content:
    print(f"Downloaded {len(content)} bytes")
    text_content = content.decode('utf-8')

# Download file to local path
server.download_file("remote_file.txt", "/path/to/local/download.txt")

# Download returns None when saving to local path
result = server.download_file("remote_file.txt", "local_copy.txt")
# result is None, but file is saved to local_copy.txt
```

## DockerSandboxedAgentServer

Runs the agent server in a local Docker container. Requires Docker to be installed and running.

### Basic Usage

```python
from openhands.sdk.sandbox import DockerSandboxedAgentServer

with DockerSandboxedAgentServer(
    base_image="nikolaik/python-nodejs:python3.12-nodejs22",
    host_port=8010,
    platform="linux/amd64",  # or "linux/arm64" for Apple Silicon
) as server:
    # Use server.base_url for connections
    conversation = Conversation(agent=agent, host=server.base_url)
    ...
```

### Parameters

- `base_image`: Base Docker image to build the agent server on
- `host_port`: Port to expose the server on (optional, auto-detected if not provided)
- `host`: Host interface to bind to (default: "127.0.0.1")
- `forward_env`: Environment variables to forward to the container (default: ["DEBUG"])
- `mount_dir`: Host directory to mount into the container (optional)
- `detach_logs`: Whether to stream container logs in the background (default: True)
- `target`: Build target ("source" or "binary", default: "source")
- `platform`: Docker platform (default: "linux/amd64")

### Examples

- `examples/23_hello_world_with_sandboxed_server.py` - Basic usage example
- `examples/27_sandboxed_server_bash_and_files.py` - Bash execution and file operations example

## RemoteSandboxedAgentServer

Runs the agent server using a remote runtime API. This is useful for cloud deployments or when you want to use a managed runtime service.

### Basic Usage

```python
from openhands.sdk.sandbox import RemoteSandboxedAgentServer

with RemoteSandboxedAgentServer(
    api_url="https://runtime-api.example.com",
    api_key="your-api-key",
    base_image="ghcr.io/all-hands-ai/agent-server:latest",
    host_port=8010,
) as server:
    # Use server.base_url for connections
    conversation = Conversation(agent=agent, host=server.base_url)
    ...
```

### Parameters

- `api_url`: Base URL of the remote runtime API
- `api_key`: API key for authentication with the runtime API
- `base_image`: Container image that includes the agent server (must be pre-built)
- `host_port`: Port to expose the server on (optional, auto-detected if not provided)
- `host`: Host interface to bind to (default: "127.0.0.1")
- `session_id`: Session ID for the runtime (optional, auto-generated if not provided)
- `resource_factor`: Resource scaling factor for the runtime (must be 1, 2, 4, or 8)
- `runtime_class`: Runtime class to use ("sysbox" or "gvisor", optional)
- `init_timeout`: Timeout for runtime initialization in seconds (default: 300.0)
- `api_timeout`: Timeout for API requests in seconds (default: 60.0)
- `keep_alive`: Whether to keep the runtime alive after closing (default: False)
- `pause_on_close`: Whether to pause the runtime instead of stopping it (default: False)

### Environment Variables

The RemoteSandboxedAgentServer requires these environment variables:

- `SANDBOX_API_KEY`: API key for the runtime service
- `SANDBOX_REMOTE_RUNTIME_API_URL`: URL of the runtime API (optional, defaults to eval server)

### Examples

- `examples/25_hello_world_with_remote_sandboxed_server.py` - Basic usage example
- `examples/27_sandboxed_server_bash_and_files.py` - Bash execution and file operations example (works with both Docker and Remote servers)

## Building Agent Server Images

For the RemoteSandboxedAgentServer, you need to use a container image that has the OpenHands agent server built in. The SDK provides utility functions to help with this:

### Quick Build and Push

```python
from openhands.sdk.sandbox import build_and_push_agent_server_image

# Build and push an agent server image
image = build_and_push_agent_server_image(
    base_image="nikolaik/python-nodejs:python3.12-nodejs22",
    registry="ghcr.io/your-org",
    image_name="agent-server",
    tag="latest",
    push=True  # Set to False to only build locally
)

# Use with RemoteSandboxedAgentServer
with RemoteSandboxedAgentServer(
    api_url="https://runtime-api.example.com",
    api_key="your-api-key",
    base_image=image,
    ...
) as server:
    pass
```

### Manual Build Process

```python
from openhands.sdk.sandbox import build_agent_server_image
import subprocess

# Build locally
local_image = build_agent_server_image(
    base_image="nikolaik/python-nodejs:python3.12-nodejs22",
    target="source",  # or "binary" for production
    variant_name="my-custom-server",
    platforms="linux/amd64",
)

# Tag for registry
registry_image = "ghcr.io/your-org/agent-server:latest"
subprocess.run(["docker", "tag", local_image, registry_image], check=True)

# Push to registry
subprocess.run(["docker", "push", registry_image], check=True)

# Use the pushed image with RemoteSandboxedAgentServer
with RemoteSandboxedAgentServer(
    api_url=runtime_api_url,
    api_key=runtime_api_key,
    base_image=registry_image,
    ...
) as server:
    ...
```

### Getting Build Instructions

```python
from openhands.sdk.sandbox import get_agent_server_build_instructions

# Print detailed build instructions
print(get_agent_server_build_instructions())
```

## Error Handling

Both implementations provide proper error handling:

- `RuntimeError`: Raised when the server fails to start or become healthy
- Connection errors are propagated from the underlying transport (Docker or HTTP)
- Cleanup is automatically handled via context manager exit

## Best Practices

1. **Use context managers**: Always use `with` statements to ensure proper cleanup
2. **Health checks**: The implementations automatically wait for the server to become healthy
3. **Resource management**: Containers/runtimes are automatically cleaned up on exit
4. **Error handling**: Wrap server startup in try/catch blocks for production use
5. **Image selection**: Use appropriate base images for your use case
6. **Port management**: Let the system auto-detect ports unless you have specific requirements

## Troubleshooting

### Docker Issues
- Ensure Docker is installed and running
- Check that the base image is available and compatible
- Verify port availability if specifying custom ports

### Remote Runtime Issues
- Verify API credentials and URL
- Check that the base image exists in the remote registry
- Ensure network connectivity to the runtime API
- Monitor initialization timeout for slow-starting containers

### General Issues
- Check logs for detailed error messages
- Verify environment variables are set correctly
- Ensure the agent server image includes all required dependencies