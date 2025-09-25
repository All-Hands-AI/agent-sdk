# syntax=docker/dockerfile:1.7

ARG BASE_IMAGE=nikolaik/python-nodejs:python3.12-nodejs22
ARG USERNAME=openhands
ARG UID=10001
ARG GID=10001
ARG PORT=8000

############################
# Builder (source mode)
# We copy source + build a venv here for local dev and debugging.
############################
FROM python:3.12-bookworm AS builder
ARG USERNAME UID GID
ENV UV_PROJECT_ENVIRONMENT=/agent-server/.venv

COPY --from=ghcr.io/astral-sh/uv /uv /uvx /bin/

RUN groupadd -g ${GID} ${USERNAME} \
 && useradd -m -u ${UID} -g ${GID} -s /usr/sbin/nologin ${USERNAME}
USER ${USERNAME}
WORKDIR /agent-server
# Cache-friendly: lockfiles first
COPY --chown=${USERNAME}:${USERNAME} pyproject.toml uv.lock README.md LICENSE ./
COPY --chown=${USERNAME}:${USERNAME} openhands ./openhands
RUN --mount=type=cache,target=/home/${USERNAME}/.cache,uid=${UID},gid=${GID} \
    uv sync --frozen --no-editable

############################
# Build a standalone binary
# We run pyinstaller here to produce openhands-agent-server
############################
FROM builder AS build-binary
ARG USERNAME UID GID

# We need --dev for pyinstaller
RUN --mount=type=cache,target=/home/${USERNAME}/.cache,uid=${UID},gid=${GID} \
    uv sync --frozen --dev --no-editable

RUN --mount=type=cache,target=/home/${USERNAME}/.cache,uid=${UID},gid=${GID} \
    uv run pyinstaller openhands/agent_server/agent-server.spec
# Fail fast if the expected binary is missing
RUN test -x /agent-server/dist/openhands-agent-server

############################
# Base runtime
############################
FROM ${BASE_IMAGE} AS base-image
ARG USERNAME UID GID PORT

# VSCode environment variables
ENV EDITOR=code \
    VISUAL=code \
    GIT_EDITOR="code --wait" \
    OPENVSCODE_SERVER_ROOT=/openhands/.openvscode-server

# NOTE: we should NOT include UV_PROJECT_ENVIRONMENT here, 
# since the agent might use it to perform other work (e.g. tools that use Python)
COPY --from=ghcr.io/astral-sh/uv /uv /uvx /bin/

# Install base packages and create user
RUN set -eux; \
    # Install base packages (works for both Debian-based images)
    apt-get update; \
    apt-get install -y --no-install-recommends \
        ca-certificates curl wget sudo apt-utils git jq tmux build-essential \
        coreutils util-linux procps findutils grep sed \
        # Docker dependencies
        apt-transport-https gnupg lsb-release; \
    \
    # Create user and group
    (getent group ${GID} || groupadd -g ${GID} ${USERNAME}); \
    (id -u ${USERNAME} >/dev/null 2>&1 || useradd -m -u ${UID} -g ${GID} -s /bin/bash ${USERNAME}); \
    # Add user to sudo group
    usermod -aG sudo ${USERNAME}; \
    echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers; \
    \
    rm -rf /var/lib/apt/lists/*

# Setup VSCode Server
ARG RELEASE_TAG="openvscode-server-v1.98.2"
ARG RELEASE_ORG="gitpod-io"

RUN set -eux; \
    # Create necessary directories
    mkdir -p $(dirname ${OPENVSCODE_SERVER_ROOT}); \
    \
    # Determine architecture
    arch=$(uname -m); \
    if [ "${arch}" = "x86_64" ]; then \
        arch="x64"; \
    elif [ "${arch}" = "aarch64" ]; then \
        arch="arm64"; \
    elif [ "${arch}" = "armv7l" ]; then \
        arch="armhf"; \
    fi; \
    \
    # Download and install VSCode Server
    wget https://github.com/${RELEASE_ORG}/openvscode-server/releases/download/${RELEASE_TAG}/${RELEASE_TAG}-linux-${arch}.tar.gz; \
    tar -xzf ${RELEASE_TAG}-linux-${arch}.tar.gz; \
    if [ -d "${OPENVSCODE_SERVER_ROOT}" ]; then rm -rf "${OPENVSCODE_SERVER_ROOT}"; fi; \
    mv ${RELEASE_TAG}-linux-${arch} ${OPENVSCODE_SERVER_ROOT}; \
    cp ${OPENVSCODE_SERVER_ROOT}/bin/remote-cli/openvscode-server ${OPENVSCODE_SERVER_ROOT}/bin/remote-cli/code; \
    rm -f ${RELEASE_TAG}-linux-${arch}.tar.gz; \
    \
    # Set proper ownership
    chown -R ${USERNAME}:${USERNAME} ${OPENVSCODE_SERVER_ROOT}

# Install Docker
RUN set -eux; \
    # Determine OS type and install Docker accordingly
    if grep -q "ubuntu" /etc/os-release; then \
        # Handle Ubuntu
        install -m 0755 -d /etc/apt/keyrings; \
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc; \
        chmod a+r /etc/apt/keyrings/docker.asc; \
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null; \
    else \
        # Handle Debian
        install -m 0755 -d /etc/apt/keyrings; \
        curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc; \
        chmod a+r /etc/apt/keyrings/docker.asc; \
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian bookworm stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null; \
    fi; \
    # Install Docker Engine, containerd, and Docker Compose
    apt-get update; \
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/*

# Configure Docker daemon with MTU 1450 to prevent packet fragmentation issues
RUN mkdir -p /etc/docker && \
    echo '{"mtu": 1450}' > /etc/docker/daemon.json

# Prepare workspace
RUN mkdir -p /workspace/project && \
    chown -R ${USERNAME}:${USERNAME} /workspace

USER ${USERNAME}
WORKDIR /
ENV LOG_JSON=true
EXPOSE ${PORT}

############################
# Target A: source
# Local dev and debugging mode: copy source + venv from builder
############################
FROM base-image AS source
ARG USERNAME
COPY --chown=${USERNAME}:${USERNAME} --from=builder /agent-server /agent-server
ENTRYPOINT ["/agent-server/.venv/bin/python","-m","openhands.agent_server"]


############################
# Target B: binary-runtime
# Production mode: build the binary inside Docker and copy it in.
# NOTE: no support for external artifact contexts anymore.
############################
FROM base-image AS binary
ARG USERNAME

COPY --chown=${USERNAME}:${USERNAME} --from=build-binary /agent-server/dist/openhands-agent-server /usr/local/bin/openhands-agent-server
RUN chmod +x /usr/local/bin/openhands-agent-server
ENTRYPOINT ["/usr/local/bin/openhands-agent-server"]
