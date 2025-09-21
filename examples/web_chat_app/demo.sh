#!/bin/bash

# OpenHands Web Chat Application Demo Script

set -e

echo "🎬 OpenHands Web Chat Application Demo"
echo "======================================"

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker and try again."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose and try again."
    exit 1
fi

# Check if .env file exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file from example..."
    cp .env.example .env
    echo "⚠️  Please edit .env file and set your LITELLM_API_KEY"
    echo "   You can get an API key from: https://docs.litellm.ai/docs/proxy/quick_start"
    echo ""
    echo "   After setting your API key, run this script again."
    exit 1
fi

# Source environment variables
source .env

# Check if API key is set
if [ -z "$LITELLM_API_KEY" ] || [ "$LITELLM_API_KEY" = "your-api-key-here" ]; then
    echo "❌ LITELLM_API_KEY is not set in .env file"
    echo "   Please edit .env file and set your API key."
    exit 1
fi

echo "✅ Environment configured"
echo "🐳 Starting Docker containers..."

# Stop any existing containers
docker-compose down 2>/dev/null || true

# Build and start the application
docker-compose up --build -d

echo "⏳ Waiting for services to start..."
sleep 10

# Check if services are running
if ! docker-compose ps | grep -q "Up"; then
    echo "❌ Services failed to start. Check logs:"
    docker-compose logs
    exit 1
fi

echo "🎉 Application started successfully!"
echo ""
echo "🌐 Web Interface: http://localhost:${WEB_PORT:-8080}"
echo "🔧 Agent Server API: http://localhost:8000"
echo ""
echo "📖 Usage Instructions:"
echo "1. Open http://localhost:${WEB_PORT:-8080} in your browser"
echo "2. Click 'New Chat' to create a conversation"
echo "3. Enter a message like 'Hello! Can you help me create a simple Python script?'"
echo "4. Watch the agent respond and use tools in real-time"
echo ""
echo "🛑 To stop the application:"
echo "   docker-compose down"
echo ""
echo "📋 To view logs:"
echo "   docker-compose logs -f"
echo ""
echo "🔍 Troubleshooting:"
echo "   - If the web interface doesn't load, wait a few more seconds"
echo "   - Check that ports 8000 and ${WEB_PORT:-8080} are not in use"
echo "   - Verify your API key has sufficient credits"

# Optional: Open browser (works on macOS and some Linux systems)
if command -v open &> /dev/null; then
    echo ""
    echo "🚀 Opening web interface in browser..."
    sleep 2
    open "http://localhost:${WEB_PORT:-8080}"
elif command -v xdg-open &> /dev/null; then
    echo ""
    echo "🚀 Opening web interface in browser..."
    sleep 2
    xdg-open "http://localhost:${WEB_PORT:-8080}"
fi