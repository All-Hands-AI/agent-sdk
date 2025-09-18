# syntax=docker/dockerfile:1.7

ARG BASE_IMAGE=nikolaik/python-nodejs:python3.12-nodejs22
ARG VARIANT=default
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
ARG USERNAME UID GID PORT VARIANT

# NOTE: we should NOT include UV_PROJECT_ENVIRONMENT here, 
# since the agent might use it to perform other work (e.g. tools that use Python)
COPY --from=ghcr.io/astral-sh/uv /uv /uvx /bin/

# Install variant-specific runtimes
RUN set -eux; \
    # Install base packages
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates curl wget; \
    \
    # Create user and group
    (getent group ${GID} || groupadd -g ${GID} ${USERNAME}); \
    (id -u ${USERNAME} >/dev/null 2>&1 || useradd -m -u ${UID} -g ${GID} -s /usr/sbin/nologin ${USERNAME}); \
    \
    # Install Java for java variant
    if [ "${VARIANT}" = "java" ]; then \
        apt-get install -y --no-install-recommends openjdk-17-jdk; \
    fi; \
    \
    # Install Go for golang variant
    if [ "${VARIANT}" = "golang" ]; then \
        GO_VERSION="1.21.5"; \
        ARCH="$(dpkg --print-architecture)"; \
        case "${ARCH}" in \
            amd64) GO_ARCH="amd64" ;; \
            arm64) GO_ARCH="arm64" ;; \
            *) echo "Unsupported architecture: ${ARCH}" && exit 1 ;; \
        esac; \
        wget -O go.tar.gz "https://golang.org/dl/go${GO_VERSION}.linux-${GO_ARCH}.tar.gz"; \
        tar -C /usr/local -xzf go.tar.gz; \
        rm go.tar.gz; \
        echo 'export PATH=/usr/local/go/bin:$PATH' >> /etc/environment; \
    fi; \
    \
    rm -rf /var/lib/apt/lists/*

# Set Go environment for golang variant
ENV PATH="${PATH}:/usr/local/go/bin"

USER ${USERNAME}
WORKDIR /agent-server
EXPOSE ${PORT}

############################
# Target A: source
# Local dev and debugging mode: copy source + venv from builder
############################
FROM base-image AS source
ARG USERNAME
COPY --chown=${USERNAME}:${USERNAME} --from=builder /agent-server /agent-server
ENTRYPOINT ["/agent-server/.venv/bin/python","-m","openhands.agent_server","--no-reload"]


############################
# Target B: binary-runtime
# Production mode: build the binary inside Docker and copy it in.
# NOTE: no support for external artifact contexts anymore.
############################
FROM base-image AS binary
ARG USERNAME

COPY --chown=${USERNAME}:${USERNAME} --from=build-binary /agent-server/dist/openhands-agent-server /usr/local/bin/openhands-agent-server
RUN chmod +x /usr/local/bin/openhands-agent-server
ENTRYPOINT ["/usr/local/bin/openhands-agent-server", "--no-reload"]
