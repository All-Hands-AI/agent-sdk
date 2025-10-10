#!/usr/bin/env bash
set -euo pipefail

# ------------------------------------------------------------
# Config (overridables)
# ------------------------------------------------------------
IMAGE="${IMAGE:-ghcr.io/all-hands-ai/agent-server}"
BASE_IMAGE="${BASE_IMAGE:-nikolaik/python-nodejs:python3.12-nodejs22}"
# Comma-separated; the FIRST is the "primary" tag used for version & cache keys
CUSTOM_TAGS="${CUSTOM_TAGS:-python}"
# Targets: prod -> binary | binary-minimal,  dev -> source | source-minimal
TARGET="${TARGET:-binary}"
PLATFORMS="${PLATFORMS:-linux/amd64,linux/arm64}"
AGENT_SDK_PATH="${AGENT_SDK_PATH:-.}"

# Validate target
case "${TARGET}" in
  binary|binary-minimal|source|source-minimal) ;;
  *) echo "[build] ERROR: Invalid TARGET '${TARGET}'. Must be one of: binary, binary-minimal, source, source-minimal" >&2; exit 1 ;;
esac

# Paths
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

# ------------------------------------------------------------
# Tag components
# ------------------------------------------------------------
IFS=',' read -ra CUSTOM_TAG_ARRAY <<< "${CUSTOM_TAGS}"
BASE_SLUG="$(echo -n "${BASE_IMAGE}" | sed -e 's|/|_s_|g' -e 's|:|_tag_|g')"
VERSIONED_TAG="v${SDK_VERSION}_${BASE_SLUG}"

# Dev/Prod classification by target
case "${TARGET}" in
  source|source-minimal) IS_DEV=1 ;;
  *) IS_DEV=0 ;;
esac

# ------------------------------------------------------------
# Cache configuration
# ------------------------------------------------------------
# Scope cache by primary tag + target to improve reuse and avoid cross-pollution
CACHE_TAG_BASE="buildcache-${TARGET}-${BASE_SLUG}"
CACHE_TAG="${CACHE_TAG_BASE}"
if [[ "${GIT_REF}" == "main" || "${GIT_REF}" == "refs/heads/main" ]]; then
  CACHE_TAG="${CACHE_TAG_BASE}-main"
elif [[ "${GIT_REF}" != "unknown" ]]; then
  SANITIZED_REF="$(echo "${GIT_REF}" | sed 's|refs/heads/||' | sed 's/[^a-zA-Z0-9.-]\+/-/g' | tr '[:upper:]' '[:lower:]')"
  CACHE_TAG="${CACHE_TAG_BASE}-${SANITIZED_REF}"
fi

# ------------------------------------------------------------
# Tagging
# ------------------------------------------------------------
TAGS=()

# SHA tags (per custom tag)
for t in "${CUSTOM_TAG_ARRAY[@]}"; do
  if [[ "${IS_DEV}" -eq 1 ]]; then
    TAGS+=( "${IMAGE}:${SHORT_SHA}-${t}-dev" )
  else
    TAGS+=( "${IMAGE}:${SHORT_SHA}-${t}" )
  fi
done

# "main" moving tag when on main
if [[ "${GIT_REF}" == "main" || "${GIT_REF}" == "refs/heads/main" ]]; then
  for t in "${CUSTOM_TAG_ARRAY[@]}"; do
    if [[ "${IS_DEV}" -eq 1 ]]; then
      TAGS+=( "${IMAGE}:main-${t}-dev" )
    else
      TAGS+=( "${IMAGE}:main-${t}" )
    fi
  done
fi

# Versioned tag (single, uses primary tag baked into VERSIONED_TAG)
if [[ "${IS_DEV}" -eq 1 ]]; then
  TAGS+=( "${IMAGE}:${VERSIONED_TAG}-dev" )
else
  TAGS+=( "${IMAGE}:${VERSIONED_TAG}" )
fi

# ------------------------------------------------------------
# Build flags
# ------------------------------------------------------------
COMMON_ARGS=(
  --build-arg "BASE_IMAGE=${BASE_IMAGE}"
  --target "${TARGET}"
  --file "${DOCKERFILE}"
  "${AGENT_SDK_PATH}"
)

echo "[build] Building target='${TARGET}' image='${IMAGE}' custom_tags='${CUSTOM_TAGS}' from base='${BASE_IMAGE}' for platforms='${PLATFORMS}'"
echo "[build] Git ref='${GIT_REF}' sha='${GIT_SHA}' version='${SDK_VERSION}'"
echo "[build] Cache tag: ${CACHE_TAG}"
echo "[build] Tags:"
printf ' - %s\n' "${TAGS[@]}" 1>&2

# ------------------------------------------------------------
# Buildx: push in CI, load locally
# ------------------------------------------------------------
if [[ -n "${GITHUB_ACTIONS:-}" || -n "${CI:-}" ]]; then
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
