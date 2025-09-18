# Docker Image Variants

The OpenHands Agent Server now supports multiple Docker image variants to accommodate different runtime requirements. Each variant includes Python 3.12 as the base runtime plus additional language runtimes as needed.

## Available Variants

### Default Variant (`default`)
- **Base Image**: `nikolaik/python-nodejs:python3.12-nodejs22`
- **Includes**: Python 3.12 + Node.js 22
- **Use Case**: General purpose agent server with JavaScript/TypeScript support
- **Tags**: 
  - `ghcr.io/all-hands-ai/agent-server:latest`
  - `ghcr.io/all-hands-ai/agent-server:<sha>`
  - `ghcr.io/all-hands-ai/agent-server:v<version>_<base_slug>`

### Java Variant (`java`)
- **Base Image**: `python:3.12-bookworm`
- **Includes**: Python 3.12 + OpenJDK 17
- **Use Case**: Agent server with Java development and execution capabilities
- **Tags**:
  - `ghcr.io/all-hands-ai/agent-server:latest-java`
  - `ghcr.io/all-hands-ai/agent-server:<sha>-java`
  - `ghcr.io/all-hands-ai/agent-server:v<version>_<base_slug>_java`

### Golang Variant (`golang`)
- **Base Image**: `python:3.12-bookworm`
- **Includes**: Python 3.12 + Go 1.21.5
- **Use Case**: Agent server with Go development and execution capabilities
- **Tags**:
  - `ghcr.io/all-hands-ai/agent-server:latest-golang`
  - `ghcr.io/all-hands-ai/agent-server:<sha>-golang`
  - `ghcr.io/all-hands-ai/agent-server:v<version>_<base_slug>_golang`

### Alpine Variant (`alpine`)
- **Base Image**: `python:3.12-alpine`
- **Includes**: Python 3.12 (minimal Alpine-based image)
- **Use Case**: Minimal footprint agent server for resource-constrained environments
- **Tags**:
  - `ghcr.io/all-hands-ai/agent-server:latest-alpine`
  - `ghcr.io/all-hands-ai/agent-server:<sha>-alpine`
  - `ghcr.io/all-hands-ai/agent-server:v<version>_<base_slug>_alpine`

## Architecture Support

All variants are built for both `linux/amd64` and `linux/arm64` architectures.

## Usage Examples

### Pull and run the default variant
```bash
docker pull ghcr.io/all-hands-ai/agent-server:latest
docker run -p 8000:8000 ghcr.io/all-hands-ai/agent-server:latest
```

### Pull and run the Java variant
```bash
docker pull ghcr.io/all-hands-ai/agent-server:latest-java
docker run -p 8000:8000 ghcr.io/all-hands-ai/agent-server:latest-java
```

### Pull and run the Golang variant
```bash
docker pull ghcr.io/all-hands-ai/agent-server:latest-golang
docker run -p 8000:8000 ghcr.io/all-hands-ai/agent-server:latest-golang
```

### Pull and run the Alpine variant
```bash
docker pull ghcr.io/all-hands-ai/agent-server:latest-alpine
docker run -p 8000:8000 ghcr.io/all-hands-ai/agent-server:latest-alpine
```

## Building Locally

You can build any variant locally using the build script:

```bash
# Build Java variant
VARIANT=java BASE_IMAGE=python:3.12-bookworm ./openhands/agent_server/docker/build.sh

# Build Golang variant
VARIANT=golang BASE_IMAGE=python:3.12-bookworm ./openhands/agent_server/docker/build.sh

# Build Alpine variant
VARIANT=alpine BASE_IMAGE=python:3.12-alpine ./openhands/agent_server/docker/build.sh

# Build default variant
VARIANT=default BASE_IMAGE=nikolaik/python-nodejs:python3.12-nodejs22 ./openhands/agent_server/docker/build.sh
```

## GitHub Actions Workflow

The variants are automatically built and pushed via GitHub Actions using a matrix strategy. Each variant is built for both amd64 and arm64 architectures in parallel.

The workflow is triggered on:
- Push to main branch
- Pull requests to main branch
- Manual workflow dispatch

## Runtime Verification

You can verify the installed runtimes in each variant:

```bash
# Check Java version
docker run --rm --entrypoint java ghcr.io/all-hands-ai/agent-server:latest-java -version

# Check Go version
docker run --rm --entrypoint go ghcr.io/all-hands-ai/agent-server:latest-golang version

# Check Python version (available in all variants)
docker run --rm --entrypoint python ghcr.io/all-hands-ai/agent-server:latest --version
```