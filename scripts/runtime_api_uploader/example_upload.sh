#!/bin/bash
# Example script showing how to use upload_docker_image.py

set -e

# Check if required environment variables are set
if [ -z "$RUNTIME_API_URL" ]; then
    echo "Error: RUNTIME_API_URL environment variable is required"
    echo "Example: export RUNTIME_API_URL=https://your-runtime-api.example.com"
    exit 1
fi

if [ -z "$RUNTIME_API_KEY" ]; then
    echo "Error: RUNTIME_API_KEY environment variable is required"
    echo "Example: export RUNTIME_API_KEY=your-api-key-here"
    exit 1
fi

# Example image name (replace with your actual image)
IMAGE_NAME="${1:-oh-agent-server-262vwoAnaZQJ2rdV4e5Is8}"

echo "=== Docker Image Upload Example ==="
echo "Runtime API URL: $RUNTIME_API_URL"
echo "Image Name: $IMAGE_NAME"
echo ""

# Run the upload script
python "$(dirname "$0")/upload_docker_image.py" "$IMAGE_NAME" latest

echo ""
echo "=== Upload Complete ==="