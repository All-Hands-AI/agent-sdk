#!/usr/bin/env python3
"""
Script to upload Docker images to Runtime-API /build endpoint.

This script:
1. Takes environment variables for Runtime API URL and key
2. Takes a Docker image name as argument
3. Pulls the image locally using docker pull
4. Creates a tar.gz of the image using docker save
5. Uploads to the /build endpoint
6. Polls /build_status until completion

Environment Variables:
- RUNTIME_API_URL: URL of the Runtime API
- RUNTIME_API_KEY: API key for authentication

Usage:
    python upload_docker_image.py <image_name> [additional_tags...]

Example:
    RUNTIME_API_URL=https://api.example.com RUNTIME_API_KEY=key123 \
    python upload_docker_image.py oh-agent-server-262vwoAnaZQJ2rdV4e5Is8 latest
"""

import argparse
import gzip
import os
import subprocess
import sys
import time

import httpx


class DockerImageUploader:
    """Handles uploading Docker images to Runtime-API."""

    def __init__(self, api_url: str, api_key: str):
        """Initialize the uploader with API credentials."""
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.session = httpx.Client(
            headers={"X-API-Key": self.api_key},
            timeout=httpx.Timeout(30.0, read=300.0),  # 5 min read timeout for uploads
        )

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup session."""
        self.session.close()

    def check_docker_available(self) -> bool:
        """Check if Docker is available and running."""
        try:
            result = subprocess.run(
                ["docker", "version"], capture_output=True, text=True, check=False
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def pull_image(self, image_name: str) -> bool:
        """Pull Docker image locally."""
        print(f"Pulling Docker image: {image_name}")
        try:
            result = subprocess.run(
                ["docker", "pull", image_name],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                print(f"Failed to pull image: {result.stderr}")
                return False
            print(f"Successfully pulled image: {image_name}")
            return True
        except Exception as e:
            print(f"Error pulling image: {e}")
            return False

    def save_image_as_tar_gz(self, image_name: str) -> bytes | None:
        """Save Docker image as tar.gz bytes."""
        print(f"Saving Docker image as tar.gz: {image_name}")
        try:
            # Use docker save to create tar
            result = subprocess.run(
                ["docker", "save", image_name], capture_output=True, check=False
            )
            if result.returncode != 0:
                print(f"Failed to save image: {result.stderr.decode()}")
                return None

            # Compress with gzip
            tar_data = result.stdout
            compressed_data = gzip.compress(tar_data)

            print(f"Image saved and compressed. Size: {len(compressed_data)} bytes")
            return compressed_data
        except Exception as e:
            print(f"Error saving image: {e}")
            return None

    def upload_image(
        self, image_data: bytes, target_image: str, tags: list[str]
    ) -> str | None:
        """Upload image to Runtime-API /build endpoint."""
        print(f"Uploading image to Runtime-API: {target_image}")

        # Prepare multipart form data
        files = {
            "context": ("image.tar.gz", image_data, "application/gzip"),
            "target_image": (None, target_image),
        }

        # Add additional tags
        for i, tag in enumerate(tags):
            files[f"tags_{i}"] = (None, tag)

        try:
            response = self.session.post(f"{self.api_url}/build", files=files)

            if response.status_code == 429:
                print("Build was rate limited. Retrying in 30 seconds...")
                time.sleep(30)
                return self.upload_image(image_data, target_image, tags)

            response.raise_for_status()

            build_data = response.json()
            build_id = build_data.get("build_id")

            if not build_id:
                print(f"No build_id in response: {build_data}")
                return None

            print(f"Build initiated with ID: {build_id}")
            return build_id

        except httpx.HTTPStatusError as e:
            print(
                f"HTTP error uploading image: {e.response.status_code} - "
                f"{e.response.text}"
            )
            return None
        except Exception as e:
            print(f"Error uploading image: {e}")
            return None

    def poll_build_status(self, build_id: str, timeout_minutes: int = 30) -> bool:
        """Poll /build_status until build is complete."""
        print(f"Polling build status for ID: {build_id}")

        start_time = time.time()
        timeout_seconds = timeout_minutes * 60

        while True:
            if time.time() - start_time > timeout_seconds:
                print(f"Build timed out after {timeout_minutes} minutes")
                return False

            try:
                response = self.session.get(
                    f"{self.api_url}/build_status", params={"build_id": build_id}
                )
                response.raise_for_status()

                status_data = response.json()
                status = status_data.get("status", "UNKNOWN")

                print(f"Build status: {status}")

                if status == "SUCCESS":
                    image_name = status_data.get("image", "unknown")
                    print(f"Build completed successfully! Image: {image_name}")
                    return True
                elif status in [
                    "FAILURE",
                    "INTERNAL_ERROR",
                    "TIMEOUT",
                    "CANCELLED",
                    "EXPIRED",
                ]:
                    error_message = status_data.get(
                        "error", f"Build failed with status: {status}"
                    )
                    print(f"Build failed: {error_message}")
                    return False
                elif status in ["PENDING", "RUNNING", "IN_PROGRESS"]:
                    # Continue polling
                    pass
                else:
                    print(f"Unknown build status: {status}")

                # Wait before next poll
                time.sleep(30)

            except httpx.HTTPStatusError as e:
                print(
                    f"HTTP error checking build status: {e.response.status_code} - "
                    f"{e.response.text}"
                )
                return False
            except Exception as e:
                print(f"Error checking build status: {e}")
                return False

    def upload_docker_image(
        self, image_name: str, additional_tags: list[str] | None = None
    ) -> bool:
        """Complete workflow to upload a Docker image."""
        additional_tags = additional_tags or []

        # Check Docker availability
        if not self.check_docker_available():
            print("Docker is not available or not running")
            return False

        # Pull image
        if not self.pull_image(image_name):
            return False

        # Save as tar.gz
        image_data = self.save_image_as_tar_gz(image_name)
        if not image_data:
            return False

        # Upload to API
        build_id = self.upload_image(image_data, image_name, additional_tags)
        if not build_id:
            return False

        # Poll until complete
        return self.poll_build_status(build_id)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Upload Docker image to Runtime-API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "image_name",
        help=(
            "Docker image name to upload (e.g., oh-agent-server-262vwoAnaZQJ2rdV4e5Is8)"
        ),
    )
    parser.add_argument("tags", nargs="*", help="Additional tags for the image")
    parser.add_argument(
        "--timeout", type=int, default=30, help="Build timeout in minutes (default: 30)"
    )

    args = parser.parse_args()

    # Get environment variables
    api_url = os.getenv("RUNTIME_API_URL")
    api_key = os.getenv("RUNTIME_API_KEY")

    if not api_url:
        print("Error: RUNTIME_API_URL environment variable is required")
        sys.exit(1)

    if not api_key:
        print("Error: RUNTIME_API_KEY environment variable is required")
        sys.exit(1)

    print(f"Runtime API URL: {api_url}")
    print(f"Image name: {args.image_name}")
    if args.tags:
        print(f"Additional tags: {args.tags}")

    # Upload image
    try:
        with DockerImageUploader(api_url, api_key) as uploader:
            success = uploader.upload_docker_image(args.image_name, args.tags)

            if success:
                print("Image upload completed successfully!")
                sys.exit(0)
            else:
                print("Image upload failed!")
                sys.exit(1)

    except KeyboardInterrupt:
        print("\nUpload interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
