# Scripts

This directory contains utility scripts for the OpenHands Agent SDK.

## runtime_api_uploader/

A collection of scripts for uploading Docker images to the Runtime-API's `/build` endpoint for deployment to Kubernetes pods.

### upload_docker_image.py

The main script to upload Docker images to the Runtime-API.

### Features

- Pulls Docker images locally using `docker pull`
- Creates compressed tar.gz archives using `docker save` and gzip
- Uploads images to Runtime-API `/build` endpoint with multipart form data
- Polls `/build_status` endpoint until build completion
- Comprehensive error handling and logging
- Rate limiting support with automatic retry

### Requirements

- Docker installed and running
- Python 3.8+ with `httpx` library
- Access to Runtime-API with valid API key

### Usage

```bash
# Set environment variables
export RUNTIME_API_URL="https://your-runtime-api.example.com"
export RUNTIME_API_KEY="your-api-key-here"

# Upload a Docker image
python scripts/runtime_api_uploader/upload_docker_image.py oh-agent-server-262vwoAnaZQJ2rdV4e5Is8

# Upload with additional tags
python scripts/runtime_api_uploader/upload_docker_image.py oh-agent-server-262vwoAnaZQJ2rdV4e5Is8 latest stable

# Set custom timeout (default: 30 minutes)
python scripts/runtime_api_uploader/upload_docker_image.py --timeout 60 oh-agent-server-262vwoAnaZQJ2rdV4e5Is8

# Or use the example script
./scripts/runtime_api_uploader/example_upload.sh oh-agent-server-262vwoAnaZQJ2rdV4e5Is8
```

### Environment Variables

- `RUNTIME_API_URL`: URL of the Runtime API (required)
- `RUNTIME_API_KEY`: API key for authentication (required)

### Exit Codes

- `0`: Success
- `1`: Error (missing environment variables, Docker issues, API errors, etc.)

### Example Output

```
Runtime API URL: https://api.example.com
Image name: oh-agent-server-262vwoAnaZQJ2rdV4e5Is8
Pulling Docker image: oh-agent-server-262vwoAnaZQJ2rdV4e5Is8
Successfully pulled image: oh-agent-server-262vwoAnaZQJ2rdV4e5Is8
Saving Docker image as tar.gz: oh-agent-server-262vwoAnaZQJ2rdV4e5Is8
Image saved and compressed. Size: 1234567 bytes
Uploading image to Runtime-API: oh-agent-server-262vwoAnaZQJ2rdV4e5Is8
Build initiated with ID: build-abc123
Polling build status for ID: build-abc123
Build status: PENDING
Build status: RUNNING
Build status: SUCCESS
Build completed successfully! Image: oh-agent-server-262vwoAnaZQJ2rdV4e5Is8:latest
Image upload completed successfully!
```

### Error Handling

The script handles various error conditions:

- Missing environment variables
- Docker daemon not running
- Image pull failures
- Network connectivity issues
- API authentication errors
- Build failures and timeouts
- Rate limiting (with automatic retry)

### Implementation Details

The script follows the same pattern as the OpenHands `RemoteRuntimeBuilder` class, using:

1. **Docker Operations**: Uses subprocess to call `docker pull` and `docker save`
2. **Compression**: Uses Python's `gzip` module to compress tar archives
3. **HTTP Client**: Uses `httpx` for robust HTTP operations with proper timeouts
4. **Multipart Upload**: Sends compressed image data as multipart form data
5. **Polling**: Continuously polls build status with 30-second intervals
6. **Context Management**: Properly manages HTTP session lifecycle