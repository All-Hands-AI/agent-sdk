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

COPY --from=ghcr.io/astral-sh/uv /uv /uvx /bin/

RUN groupadd -g ${GID} ${USERNAME} \
 && useradd -m -u ${UID} -g ${GID} -s /usr/sbin/nologin ${USERNAME}
USER ${USERNAME}
WORKDIR /src

# Cache-friendly: lockfiles first
COPY --chown=${USERNAME}:${USERNAME} pyproject.toml uv.lock README.md LICENSE ./
COPY --chown=${USERNAME}:${USERNAME} openhands ./openhands
RUN --mount=type=cache,target=/home/${USERNAME}/.cache,uid=${UID},gid=${GID} \
    uv venv && . .venv/bin/activate && uv sync --frozen --dev

RUN . .venv/bin/activate && \
    uv pip install -e openhands/sdk -e openhands/tools -e openhands/agent_server

############################
# Build a standalone binary
# We run build.py here to produce openhands-agent-server
############################
FROM builder AS build-binary
ARG USERNAME UID GID

RUN --mount=type=cache,target=/home/${USERNAME}/.cache,uid=${UID},gid=${GID} \
    uv run pyinstaller openhands/agent_server/agent-server.spec && \
    mkdir -p /src/dist && \
    mv /src/openhands/agent_server/dist/openhands-agent-server /src/dist/
# Fail fast if the expected binary is missing
RUN test -x /src/dist/openhands-agent-server

############################
# Base runtime
############################
FROM ${BASE_IMAGE} AS base-image
ARG USERNAME UID GID PORT
RUN (getent group ${GID} || groupadd -g ${GID} ${USERNAME}) && \
    (id -u ${USERNAME} >/dev/null 2>&1 || useradd -m -u ${UID} -g ${GID} -s /usr/sbin/nologin ${USERNAME}) && \
    (command -v apt-get >/dev/null && apt-get update && \
     apt-get install -y --no-install-recommends ca-certificates && \
     rm -rf /var/lib/apt/lists/*) || true
USER ${USERNAME}
WORKDIR /agent-server
EXPOSE ${PORT}

############################
# Target A: source
# Local dev and debugging mode: copy source + venv from builder
############################
FROM base-image AS source
ARG USERNAME

COPY --chown=${USERNAME}:${USERNAME} --from=builder /src/.venv /agent-server/.venv
COPY --chown=${USERNAME}:${USERNAME} --from=builder /src /agent-server
# We do it explictly instead of $PATH to prevent LLM agent accidentally using
# the venv's python for its own work.
# ENTRYPOINT ["/agent-server/.venv/bin/uvicorn", "openhands.agent_server"]

############################
# Target B: binary-runtime
# Production mode: build the binary inside Docker and copy it in.
# NOTE: no support for external artifact contexts anymore.
############################
FROM base-image AS binary
ARG USERNAME

COPY --chown=${USERNAME}:${USERNAME} --from=build-binary /src/dist/openhands-agent-server /usr/local/bin/openhands-agent-server
RUN chmod +x /usr/local/bin/openhands-agent-server
ENTRYPOINT ["/usr/local/bin/openhands-agent-server"]
