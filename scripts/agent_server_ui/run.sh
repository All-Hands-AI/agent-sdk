#!/bin/bash

# Script to run the web chat app example using its configuration
set -euo pipefail

# Set the CWD to the current directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
# Change to the script's directory before spawning the process
cd "$SCRIPT_DIR"

export OPENHANDS_AGENT_SERVER_CONFIG_PATH="config.json"
python -m openhands.agent_server 
