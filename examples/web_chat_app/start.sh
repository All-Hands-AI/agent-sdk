#!/bin/bash

# OpenHands Web Chat Application Startup Script

set -e

echo "🚀 Starting OpenHands Web Chat Application..."

# Check if .env file exists, if not copy from example
if [ ! -f .env ]; then
    echo "📝 Creating .env file from example..."
    cp .env.example .env
    echo "⚠️  Please edit .env file and set your LITELLM_API_KEY before running again."
    exit 1
fi

# Source environment variables
source .env

# Check if API key is set
if [ -z "$LITELLM_API_KEY" ] || [ "$LITELLM_API_KEY" = "your-api-key-here" ]; then
    echo "❌ Error: LITELLM_API_KEY is not set in .env file"
    echo "Please edit .env file and set your API key."
    exit 1
fi

echo "✅ Environment configured"
echo "🌐 Web interface will be available at: http://localhost:${WEB_PORT:-8080}"
echo "🔧 Agent server will be available at: http://localhost:${AGENT_SERVER_PORT:-8000}"

# Start the application
echo "🐳 Starting Docker containers..."
docker-compose up --build

echo "🎉 Application started successfully!"