#!/bin/bash

# Script to run the web chat app example using its configuration
set -euo pipefail

export OPENHANDS_AGENT_SERVER_CONFIG_PATH="openhands_agent_server_config.json"

python -m openhands.agent_server 
