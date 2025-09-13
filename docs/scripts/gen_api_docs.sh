#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || (cd "$SCRIPT_DIR/../.." && pwd))"
cd "$REPO_ROOT"

# Clean old docs
rm -rf docs/reference/sdk docs/reference/tools
mkdir -p docs/reference/sdk docs/reference/tools

# Generate SDK docs
PYTHONPATH="$REPO_ROOT" uv run griffe2md openhands.sdk -o docs/reference/sdk.mdx

# Generate Tools docs
PYTHONPATH="$REPO_ROOT" uv run griffe2md openhands.tools -o docs/reference/tools.mdx

echo "✅ Docs regenerated under docs/reference/"
