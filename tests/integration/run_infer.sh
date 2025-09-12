#!/usr/bin/env bash
set -eo pipefail

# Check for help flag
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
  echo "Usage: $0 [LITELLM_MODEL] [LITELLM_API_KEY] [LITELLM_BASE_URL] [NUM_WORKERS] [EVAL_IDS] [RUN_NAME]"
  echo ""
  echo "Arguments:"
  echo "  LITELLM_MODEL     LLM model to use (default: litellm_proxy/anthropic/claude-sonnet-4-20250514)"
  echo "  LITELLM_API_KEY   API key for LiteLLM (optional, can use env var)"
  echo "  LITELLM_BASE_URL  Base URL for LiteLLM (optional, can use env var)"
  echo "  NUM_WORKERS       Number of parallel workers (default: 1)"
  echo "  EVAL_IDS          Comma-separated list of test IDs to run (optional)"
  echo "  RUN_NAME          Name for this run (optional)"
  echo ""
  echo "Example:"
  echo "  $0 litellm_proxy/anthropic/claude-sonnet-4-20250514 \"\$API_KEY\" \"\" 1 \"t01_fix_simple_typo_class_based\" \"test_run\""
  exit 0
fi

LITELLM_MODEL=$1
LITELLM_API_KEY=$2
LITELLM_BASE_URL=$3
NUM_WORKERS=$4
EVAL_IDS=$5
RUN_NAME=$6

if [ -z "$NUM_WORKERS" ]; then
  NUM_WORKERS=1
  echo "Number of workers not specified, use default $NUM_WORKERS"
fi

if [ -z "$LITELLM_MODEL" ]; then
  echo "LLM model not specified, use default litellm_proxy/anthropic/claude-sonnet-4-20250514"
  LITELLM_MODEL="litellm_proxy/anthropic/claude-sonnet-4-20250514"
fi

# Get agent-sdk version from git
AGENT_SDK_VERSION=$(git rev-parse --short HEAD)

echo "LITELLM_MODEL: $LITELLM_MODEL"
echo "AGENT_SDK_VERSION: $AGENT_SDK_VERSION"
echo "NUM_WORKERS: $NUM_WORKERS"

EVAL_NOTE=$AGENT_SDK_VERSION

# Set run name for output directory
if [ -n "$RUN_NAME" ]; then
  EVAL_NOTE="${EVAL_NOTE}_${RUN_NAME}"
fi

# Build the command to run the Python script
COMMAND="uv run python tests/integration/run_infer.py \
  --llm-model $LITELLM_MODEL \
  --num-workers $NUM_WORKERS \
  --eval-note $EVAL_NOTE"

# Add API key if provided
if [ -n "$LITELLM_API_KEY" ]; then
  echo "Using provided LITELLM_API_KEY"
  export LITELLM_API_KEY="$LITELLM_API_KEY"
fi

# Add base URL if provided
if [ -n "$LITELLM_BASE_URL" ]; then
  echo "Using provided LITELLM_BASE_URL: $LITELLM_BASE_URL"
  export LITELLM_BASE_URL="$LITELLM_BASE_URL"
fi

# Add specific test IDs if provided
if [ -n "$EVAL_IDS" ]; then
  echo "EVAL_IDS: $EVAL_IDS"
  COMMAND="$COMMAND --eval-ids $EVAL_IDS"
fi

# Run the command
echo "Running command: $COMMAND"
eval $COMMAND