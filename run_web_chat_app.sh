#!/bin/bash

# Script to run the web chat app example using its configuration
set -euo pipefail

# Colors for output
GREEN='\033[32m'
YELLOW='\033[33m'
RED='\033[31m'
CYAN='\033[36m'
RESET='\033[0m'

# Get script directory and project paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEB_CHAT_APP_DIR="${SCRIPT_DIR}/examples/server_sdk/webhook/web_chat_app"
CONFIG_FILE="${WEB_CHAT_APP_DIR}/agent_server_config.json"
WEB_DIR="${WEB_CHAT_APP_DIR}/web"

echo -e "${CYAN}🚀 Starting OpenHands Web Chat App${RESET}"

# Verify the config file exists
if [[ ! -f "$CONFIG_FILE" ]]; then
    echo -e "${RED}❌ Config file not found: $CONFIG_FILE${RESET}"
    echo "Make sure you're running this script from the agent-sdk root directory."
    exit 1
fi

# Verify the web directory exists
if [[ ! -d "$WEB_DIR" ]]; then
    echo -e "${RED}❌ Web directory not found: $WEB_DIR${RESET}"
    exit 1
fi

echo -e "${YELLOW}📁 Working directory: $WEB_CHAT_APP_DIR${RESET}"
echo -e "${YELLOW}⚙️  Config file: $CONFIG_FILE${RESET}"
echo -e "${YELLOW}🌐 Web files: $WEB_DIR${RESET}"
echo -e "${GREEN}🔗 Server will be available at: http://localhost:8000${RESET}"
echo -e "${GREEN}📖 API docs will be available at: http://localhost:8000/docs${RESET}"
echo -e "${GREEN}🎯 Web app will be available at: http://localhost:8000/static/${RESET}"
echo

# Set the config file path environment variable
export OPENHANDS_AGENT_SERVER_CONFIG_PATH="$CONFIG_FILE"

# Unset session API key for local development (disable authentication)
if [ -n "$SESSION_API_KEY" ]; then
    unset SESSION_API_KEY
    echo -e "${YELLOW}🔓 Disabled authentication for local development${RESET}"
fi

# Start the server using uv (run from project root for proper module imports)
echo -e "${CYAN}Starting server...${RESET}"
cd "$SCRIPT_DIR"
uv run python -m openhands.agent_server --host 0.0.0.0 --port 8000 --reload