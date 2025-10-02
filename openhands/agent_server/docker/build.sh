#!/usr/bin/env bash
set -euo pipefail

# ------------------------------------------------------------
# Config (overridables)
# ------------------------------------------------------------
IMAGE="${IMAGE:-ghcr.io/all-hands-ai/agent-server}"
BASE_IMAGE="${BASE_IMAGE:-nikolaik/python-nodejs:python3.12-nodejs22}"
VARIANT_NAME="${VARIANT_NAME:-python}"  # "python", "java", or "golang"
TARGET="${TARGET:-binary}"          # "binary" (prod) or "source" (dev)
PLATFORMS="${PLATFORMS:-linux/amd64,linux/arm64}"

# Path to Dockerfile (in script dir, not cwd)
SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)"
DOCKERFILE="${SCRIPT_DIR}/Dockerfile"

[[ -f "${DOCKERFILE}" ]] || { echo "[build] ERROR: Dockerfile not found at ${DOCKERFILE}"; exit 1; }

# ------------------------------------------------------------
# Git info (don’t break userspace tagging)
# ------------------------------------------------------------
GIT_SHA="${GITHUB_SHA:-$(git rev-parse --verify HEAD 2>/dev/null || echo unknown)}"
SHORT_SHA="${GIT_SHA:0:7}"
GIT_REF="${GITHUB_REF:-$(git symbolic-ref -q --short HEAD 2>/dev/null || echo unknown)}"

# ------------------------------------------------------------
# Version tag from package (best-effort; fall back to 0.0.0)
# ------------------------------------------------------------
SDK_VERSION="$(python - <<'PY' 2>/dev/null || echo 0.0.0
from importlib.metadata import version
print(version("openhands-sdk"))
PY
)"
echo "[build] Using SDK version ${SDK_VERSION}"

# Base slug (keep legacy format so downstream tags don’t change)
BASE_SLUG="$(echo -n "${BASE_IMAGE}" | sed -e 's|/|_s_|g' -e 's|:|_tag_|g')"
VERSIONED_TAG="v${SDK_VERSION}_${BASE_SLUG}_${VARIANT_NAME}"

# ------------------------------------------------------------
# Cache configuration
# ------------------------------------------------------------
CACHE_TAG_BASE="buildcache-${VARIANT_NAME}"
CACHE_TAG="${CACHE_TAG_BASE}"

# Add branch-specific cache tag for better cache hits
if [[ "${GIT_REF}" == "main" || "${GIT_REF}" == "refs/heads/main" ]]; then
  CACHE_TAG="${CACHE_TAG_BASE}-main"
elif [[ "${GIT_REF}" != "unknown" ]]; then
  # Sanitize branch name for use in cache tag
  SANITIZED_REF="$(echo "${GIT_REF}" | sed 's|refs/heads/||' | sed 's/[^a-zA-Z0-9.-]\+/-/g' | tr '[:upper:]' '[:lower:]')"
  CACHE_TAG="${CACHE_TAG_BASE}-${SANITIZED_REF}"
fi

# ------------------------------------------------------------
# Tagging: prod vs dev
# ------------------------------------------------------------
if [[ "${TARGET}" == "source" ]]; then
  # Dev tags: add -dev suffix
  TAGS=( "${IMAGE}:${SHORT_SHA}-${VARIANT_NAME}-dev" "${IMAGE}:${VERSIONED_TAG}-dev" )
  if [[ "${GIT_REF}" == "main" || "${GIT_REF}" == "refs/heads/main" ]]; then
    TAGS+=( "${IMAGE}:latest-${VARIANT_NAME}-dev" )
  fi
else
  # Prod tags
  TAGS=( "${IMAGE}:${SHORT_SHA}-${VARIANT_NAME}" "${IMAGE}:${VERSIONED_TAG}" )
  if [[ "${GIT_REF}" == "main" || "${GIT_REF}" == "refs/heads/main" ]]; then
    TAGS+=( "${IMAGE}:latest-${VARIANT_NAME}" )
  fi
fi

# ------------------------------------------------------------
# Build flags
# ------------------------------------------------------------
AGENT_SDK_PATH="${AGENT_SDK_PATH:-.}"
COMMON_ARGS=(
  --build-arg "BASE_IMAGE=${BASE_IMAGE}"
  --target "${TARGET}"
  --file "${DOCKERFILE}"
  $AGENT_SDK_PATH
)

echo "[build] Building target='${TARGET}' image='${IMAGE}' variant='${VARIANT_NAME}' from base='${BASE_IMAGE}' for platforms='${PLATFORMS}'"
echo "[build] Git ref='${GIT_REF}' sha='${GIT_SHA}' version='${SDK_VERSION}'"
echo "[build] Cache tag: ${CACHE_TAG}"
echo "[build] Tags:"
printf ' - %s\n' "${TAGS[@]}" 1>&2

# ------------------------------------------------------------
# Buildx: push in CI, load locally
# ------------------------------------------------------------
if [[ -n "${GITHUB_ACTIONS:-}" || -n "${CI:-}" ]]; then
  # CI: multi-arch, push with caching
  docker buildx create --use --name agentserver-builder >/dev/null 2>&1 || true
  docker buildx build \
    --platform "${PLATFORMS}" \
    "${COMMON_ARGS[@]}" \
    $(printf ' --tag %q' "${TAGS[@]}") \
    --cache-from="type=registry,ref=${IMAGE}:${CACHE_TAG}" \
    --cache-from="type=registry,ref=${IMAGE}:${CACHE_TAG_BASE}-main" \
    --cache-to="type=registry,ref=${IMAGE}:${CACHE_TAG},mode=max" \
    --push
else
  # Local: single-arch, load to docker with caching
  docker buildx build \
    "${COMMON_ARGS[@]}" \
    $(printf ' --tag %q' "${TAGS[@]}") \
    --cache-from="type=registry,ref=${IMAGE}:${CACHE_TAG}" \
    --cache-from="type=registry,ref=${IMAGE}:${CACHE_TAG_BASE}-main" \
    --load
fi

echo "[build] Done. Tags:"
printf ' - %s\n' "${TAGS[@]}"


# ------------------------------------------------------------
# GitHub Actions outputs (if available)
# ------------------------------------------------------------
if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  {
    printf 'image=%s\n' "${IMAGE}"
    printf 'short_sha=%s\n' "${SHORT_SHA}"
    printf 'versioned_tag=%s\n' "${VERSIONED_TAG}"
    printf 'tags_csv=%s\n' "$(IFS=, ; echo "${TAGS[*]}")"
  } >> "$GITHUB_OUTPUT"

  {
    echo 'tags<<EOF'
    printf '%s\n' "${TAGS[@]}"
    echo 'EOF'
  } >> "$GITHUB_OUTPUT"
fi
