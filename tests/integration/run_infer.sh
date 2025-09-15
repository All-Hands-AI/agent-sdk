#!/usr/bin/env bash
set -eo pipefail

# Check for help flag
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
  echo "Usage: $0 [LLM_CONFIG] [LLM_API_KEY] [LLM_BASE_URL] [NUM_WORKERS] [EVAL_IDS] [RUN_NAME]"
  echo ""
  echo "Arguments:"
  echo "  LLM_CONFIG        LLM configuration JSON (required)"
  echo "  LLM_API_KEY       API key for LLM service (optional, can use env var)"
  echo "  LLM_BASE_URL      Base URL for LLM service (optional, can use env var)"
  echo "  NUM_WORKERS       Number of parallel workers (default: 1)"
  echo "  EVAL_IDS          Comma-separated list of test IDs to run (optional)"
  echo "  RUN_NAME          Name for this run (optional)"
  echo ""
  echo "Example:"
  echo "  $0 '{\"model\":\"litellm_proxy/anthropic/claude-sonnet-4-20250514\",\"temperature\":0.0}' \"api_key\" \"base_url\" 1 \"t01_fix_simple_typo_class_based\" \"test_run\""
  exit 0
fi

LLM_CONFIG=$1
LLM_API_KEY_PARAM=$2
LLM_BASE_URL_PARAM=$3
NUM_WORKERS=$4
EVAL_IDS=$5
RUN_NAME=$6

if [ -z "$LLM_CONFIG" ]; then
  echo "Error: LLM_CONFIG is required as first parameter!"
  echo "Use --help for usage information"
  exit 1
fi

if [ -z "$NUM_WORKERS" ]; then
  NUM_WORKERS=1
  echo "Number of workers not specified, use default $NUM_WORKERS"
fi

# Set environment variables if provided as parameters
if [ -n "$LLM_API_KEY_PARAM" ]; then
  export LLM_API_KEY="$LLM_API_KEY_PARAM"
fi

if [ -n "$LLM_BASE_URL_PARAM" ]; then
  export LLM_BASE_URL="$LLM_BASE_URL_PARAM"
fi

# Get agent-sdk version from git
AGENT_SDK_VERSION=$(git rev-parse --short HEAD)

echo "LLM_CONFIG: $LLM_CONFIG"
echo "AGENT_SDK_VERSION: $AGENT_SDK_VERSION"
echo "NUM_WORKERS: $NUM_WORKERS"

EVAL_NOTE=$AGENT_SDK_VERSION

# Set run name for output directory
if [ -n "$RUN_NAME" ]; then
  EVAL_NOTE="${EVAL_NOTE}_${RUN_NAME}"
fi

# Build the command to run the Python script
COMMAND="uv run python tests/integration/run_infer.py \
  --llm-config '$LLM_CONFIG' \
  --num-workers $NUM_WORKERS \
  --eval-note $EVAL_NOTE"

# Add specific test IDs if provided
if [ -n "$EVAL_IDS" ]; then
  echo "EVAL_IDS: $EVAL_IDS"
  COMMAND="$COMMAND --eval-ids $EVAL_IDS"
fi

# Run the command
echo "Running command: $COMMAND"
eval $COMMAND