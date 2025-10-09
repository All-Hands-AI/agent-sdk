# Runtime API Uploader

Scripts for uploading Docker images to the Runtime-API's `/build` endpoint for deployment to Kubernetes pods.

## Files

- `upload_docker_image.py` - Main script for uploading Docker images
- `example_upload.sh` - Example shell script showing usage
- `README.md` - This documentation file

## Quick Start

1. Set environment variables:
```bash
export RUNTIME_API_URL="https://your-runtime-api.example.com"
export RUNTIME_API_KEY="your-api-key-here"
```

2. Upload a Docker image:
```bash
python upload_docker_image.py oh-agent-server-262vwoAnaZQJ2rdV4e5Is8
```

Or use the example script:
```bash
./example_upload.sh oh-agent-server-262vwoAnaZQJ2rdV4e5Is8
```

## Features

- Pulls Docker images locally using `docker pull`
- Creates compressed tar.gz archives using `docker save` and gzip
- Uploads images to Runtime-API `/build` endpoint with multipart form data
- Polls `/build_status` endpoint until build completion
- Comprehensive error handling and logging
- Rate limiting support with automatic retry

## Requirements

- Docker installed and running
- Python 3.8+ with `httpx` library
- Access to Runtime-API with valid API key

## Usage

```bash
python upload_docker_image.py [OPTIONS] IMAGE_NAME [TAGS...]
```

### Arguments

- `IMAGE_NAME` - Docker image name to upload (e.g., `oh-agent-server-262vwoAnaZQJ2rdV4e5Is8`)
- `TAGS` - Additional tags for the image (optional)

### Options

- `--timeout TIMEOUT` - Build timeout in minutes (default: 30)
- `--help` - Show help message

### Environment Variables

- `RUNTIME_API_URL` - URL of the Runtime API (required)
- `RUNTIME_API_KEY` - API key for authentication (required)

## Examples

```bash
# Basic upload
python upload_docker_image.py oh-agent-server-262vwoAnaZQJ2rdV4e5Is8

# Upload with additional tags
python upload_docker_image.py oh-agent-server-262vwoAnaZQJ2rdV4e5Is8 latest stable

# Set custom timeout
python upload_docker_image.py --timeout 60 oh-agent-server-262vwoAnaZQJ2rdV4e5Is8

# Using the example script
./example_upload.sh my-custom-image
```

## Error Handling

The script handles various error conditions:

- Missing environment variables
- Docker daemon not running
- Image pull failures
- Network connectivity issues
- API authentication errors
- Build failures and timeouts
- Rate limiting (with automatic retry)

## Implementation Details

The script follows the same pattern as the OpenHands `RemoteRuntimeBuilder` class:

1. **Docker Operations** - Uses subprocess to call `docker pull` and `docker save`
2. **Compression** - Uses Python's `gzip` module to compress tar archives
3. **HTTP Client** - Uses `httpx` for robust HTTP operations with proper timeouts
4. **Multipart Upload** - Sends compressed image data as multipart form data
5. **Polling** - Continuously polls build status with 30-second intervals
6. **Context Management** - Properly manages HTTP session lifecycle