#!/usr/bin/env python3
"""
Runtime Build Context Generator for OpenHands Agent Server

This script creates a tar.gz file containing everything needed
to build the agent-server in a runtime environment.
The resulting tar.gz will have a Dockerfile at the top level
and all necessary source code and dependencies.

If RUNTIME_API_URL and RUNTIME_API_KEY are set, it will upload
the build context to the runtime API and poll for completion.
"""

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

import httpx


class BuildConfig:
    """Configuration for the build process."""

    def __init__(self):
        self.output_dir = os.getenv("OUTPUT_DIR", "./runtime-build")
        self.base_image = os.getenv(
            "BASE_IMAGE", "nikolaik/python-nodejs:python3.12-nodejs22"
        )
        self.target = os.getenv("TARGET", "binary")
        self.clean_output = os.getenv("CLEAN_OUTPUT", "true").lower() == "true"
        self.custom_tags = os.getenv("CUSTOM_TAGS", "python")
        self.output_name = os.getenv("OUTPUT_NAME")

        # Runtime API configuration
        self.runtime_api_url = os.getenv("RUNTIME_API_URL", "")
        self.runtime_api_key = os.getenv("RUNTIME_API_KEY", "")

        # Git information
        self.git_sha = self._get_git_sha()
        self.short_sha = self.git_sha[:7]
        self.primary_tag = self.custom_tags.split(",")[0]

        # Generate output filename
        if self.output_name:
            self.output_filename = self.output_name
        else:
            self.output_filename = (
                f"agent-server-{self.short_sha}-{self.primary_tag}.tar.gz"
            )

        # Validate target
        valid_targets = ["binary", "binary-minimal", "source", "source-minimal"]
        if self.target not in valid_targets:
            raise ValueError(
                f"Invalid TARGET '{self.target}'. Must be one of: "
                f"{', '.join(valid_targets)}"
            )

    def _get_git_sha(self) -> str:
        """Get the current git SHA."""
        github_sha = os.getenv("GITHUB_SHA")
        if github_sha:
            return github_sha

        try:
            result = subprocess.run(
                ["git", "rev-parse", "--verify", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return "unknown"


class Logger:
    """Simple logger with timestamps."""

    @staticmethod
    def info(message: str) -> None:
        """Log an info message."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [runtime-build] {message}")

    @staticmethod
    def error(message: str) -> None:
        """Log an error message."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [runtime-build] ERROR: {message}", file=sys.stderr)


class DockerfileGenerator:
    """Generates Dockerfiles for different build targets."""

    def __init__(self, config: BuildConfig):
        self.config = config

    def generate(self) -> str:
        """Generate Dockerfile content based on target."""
        if self.config.target in ["binary", "binary-minimal"]:
            return self._generate_binary_dockerfile()
        else:  # source, source-minimal
            return self._generate_source_dockerfile()

    def _generate_binary_dockerfile(self) -> str:
        """Generate Dockerfile for binary targets."""
        minimal_suffix = "-minimal" if "minimal" in self.config.target else ""

        dockerfile_comment = (
            f"# Generated Dockerfile for OpenHands Agent Server "
            f"(binary{minimal_suffix})"
        )
        return f"""{dockerfile_comment}
FROM {self.config.base_image}

# Set working directory
WORKDIR /app

# Copy source code
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -e ./openhands/sdk
RUN pip install --no-cache-dir -e ./openhands/tools
RUN pip install --no-cache-dir -e ./openhands/workspace
RUN pip install --no-cache-dir -e ./openhands/agent_server

# Expose port
EXPOSE 8000

# Set entrypoint
CMD ["python", "-m", "openhands.agent_server.server"]
"""

    def _generate_source_dockerfile(self) -> str:
        """Generate Dockerfile for source targets."""
        minimal_suffix = "-minimal" if "minimal" in self.config.target else ""

        dockerfile_comment = (
            f"# Generated Dockerfile for OpenHands Agent Server "
            f"(source{minimal_suffix})"
        )
        return f"""{dockerfile_comment}
FROM {self.config.base_image}

# Set working directory
WORKDIR /app

# Copy source code
COPY . .

# Install in development mode
RUN pip install --no-cache-dir -e ./openhands/sdk
RUN pip install --no-cache-dir -e ./openhands/tools
RUN pip install --no-cache-dir -e ./openhands/workspace
RUN pip install --no-cache-dir -e ./openhands/agent_server

# Expose port
EXPOSE 8000

# Set entrypoint for development
CMD ["python", "-m", "openhands.agent_server.server", "--dev"]
"""


class BuildContextCreator:
    """Creates the build context tar.gz file."""

    def __init__(self, config: BuildConfig):
        self.config = config
        self.script_dir = Path(__file__).parent.absolute()
        self.repo_root = self.script_dir.parent.parent.parent

    def create(self) -> Path:
        """Create the build context tar.gz file."""
        Logger.info(f"Creating build context for target: {self.config.target}")
        Logger.info(f"Base image: {self.config.base_image}")
        Logger.info(f"Git SHA: {self.config.git_sha}")

        # Prepare output directory
        output_dir = Path(self.config.output_dir)
        if self.config.clean_output and output_dir.exists():
            Logger.info(f"Cleaning output directory: {output_dir}")
            shutil.rmtree(output_dir)

        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / self.config.output_filename

        # Create temporary directory for build context
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Generate Dockerfile
            dockerfile_generator = DockerfileGenerator(self.config)
            dockerfile_content = dockerfile_generator.generate()

            dockerfile_path = temp_path / "Dockerfile"
            dockerfile_path.write_text(dockerfile_content)
            Logger.info("Generated Dockerfile")

            # Copy source code
            self._copy_source_code(temp_path)

            # Create tar.gz
            self._create_tarball(temp_path, output_path)

        Logger.info(f"Build context created: {output_path}")
        Logger.info(
            f"File size: {self._format_size(float(output_path.stat().st_size))}"
        )

        return output_path

    def _copy_source_code(self, dest_dir: Path) -> None:
        """Copy necessary source code to the build context."""
        Logger.info("Copying source code...")

        # Directories to copy
        dirs_to_copy = [
            "openhands/sdk",
            "openhands/tools",
            "openhands/workspace",
            "openhands/agent_server",
        ]

        for dir_name in dirs_to_copy:
            src_dir = self.repo_root / dir_name
            dest_subdir = dest_dir / dir_name

            if src_dir.exists():
                Logger.info(f"Copying {dir_name}...")
                shutil.copytree(src_dir, dest_subdir, ignore=self._ignore_patterns)
            else:
                Logger.error(f"Source directory not found: {src_dir}")
                raise FileNotFoundError(f"Required directory not found: {src_dir}")

        # Copy root files
        root_files = ["pyproject.toml", "uv.lock", "README.mdx"]
        for file_name in root_files:
            src_file = self.repo_root / file_name
            if src_file.exists():
                shutil.copy2(src_file, dest_dir / file_name)
                Logger.info(f"Copied {file_name}")

    def _ignore_patterns(self, dir_path: str, names: list[str]) -> list[str]:
        """Ignore patterns for copying source code."""
        ignore_patterns = {
            "__pycache__",
            "*.pyc",
            "*.pyo",
            "*.pyd",
            ".pytest_cache",
            ".coverage",
            "*.egg-info",
            ".git",
            ".gitignore",
            "node_modules",
            ".DS_Store",
            "Thumbs.db",
        }

        ignored = []
        for name in names:
            if name in ignore_patterns or any(
                name.endswith(pattern.lstrip("*"))
                for pattern in ignore_patterns
                if pattern.startswith("*")
            ):
                ignored.append(name)

        return ignored

    def _create_tarball(self, source_dir: Path, output_path: Path) -> None:
        """Create the tar.gz file."""
        Logger.info(f"Creating tarball: {output_path}")

        with tarfile.open(output_path, "w:gz") as tar:
            for item in source_dir.iterdir():
                tar.add(item, arcname=item.name)

    def _format_size(self, size_bytes: float) -> str:
        """Format file size in human readable format."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f}{unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f}TB"


class RuntimeAPIClient:
    """Client for interacting with the Runtime API."""

    def __init__(self, config: BuildConfig):
        self.config = config
        self.base_url = config.runtime_api_url.rstrip("/")
        self.headers = {
            "X-API-Key": config.runtime_api_key,
        }

    def upload_and_build(self, tar_path: Path) -> bool:
        """Upload build context and monitor the build process."""
        if not self.config.runtime_api_url or not self.config.runtime_api_key:
            Logger.info("Runtime API credentials not provided, skipping upload")
            return True

        Logger.info("📤 Uploading build context to Runtime API...")

        # Encode tar.gz file as base64
        try:
            with open(tar_path, "rb") as f:
                encoded_context = base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            Logger.error(f"❌ Failed to encode tar.gz file: {e}")
            return False

        # Upload build context
        try:
            with httpx.Client(headers=self.headers) as client:
                # Get the registry prefix - we need to know what to call this thing...
                response = client.get(f"{self.base_url}/registry_prefix")
                response_json = response.json()
                registry_prefix = response_json["registry_prefix"]

                # Prepare payload
                target_image = (
                    f"{registry_prefix}/agent-server:{self.config.short_sha}"
                    f"-{self.config.primary_tag}"
                )
                files = [
                    ("context", ("context.tar.gz", encoded_context)),
                    ("target_image", (None, target_image)),
                ]
                response = client.post(
                    f"{self.base_url}/build",
                    files=files,
                    timeout=300,  # 5 minutes timeout for upload
                )
                response.raise_for_status()

                build_data = response.json()
                build_id = build_data.get("build_id")

                if not build_id:
                    Logger.error("No build_id returned from Runtime API")
                    return False

                Logger.info(f"🛠️  Build started with ID: {build_id}")
                Logger.info(f"🎯 Target image: {target_image}")

                # Poll for build completion
                return self._poll_build_status(build_id)

        except httpx.RequestError as e:
            Logger.error(f"Failed to upload to Runtime API: {e}")
            return False
        except httpx.HTTPStatusError as e:
            Logger.error(f"HTTP error from Runtime API: {e}")
            return False
        except json.JSONDecodeError as e:
            Logger.error(f"Invalid JSON response from Runtime API: {e}")
            return False

    def _poll_build_status(self, build_id: str) -> bool:
        """Poll the build status until completion."""
        Logger.info("Monitoring build progress...")

        max_attempts = 60  # 10 minutes with 10-second intervals
        attempt = 0

        while attempt < max_attempts:
            try:
                with httpx.Client() as client:
                    response = client.get(
                        f"{self.base_url}/build_status",
                        params={"build_id": build_id},
                        headers=self.headers,
                        timeout=30,
                    )
                    response.raise_for_status()

                    status_data = response.json()
                    status = status_data.get("status", "unknown")

                    Logger.info(f"Build status: {status}")

                    if status == "SUCCESS":
                        Logger.info("✅ Build completed successfully!")
                        return True
                    elif status in (
                        "FAILURE",
                        "INTERNAL_ERROR",
                        "TIMEOUT",
                        "CANCELLED",
                        "EXPIRED",
                    ):
                        error_msg = status_data.get("error", "Unknown error")
                        Logger.error(f"❌ Build failed: {error_msg}")
                        return False

                    # Continue polling
                    time.sleep(10)
                    attempt += 1

            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                Logger.error(f"Failed to check build status: {e}")
                time.sleep(10)
                attempt += 1

        Logger.error("⏰ Build monitoring timed out")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate build context for OpenHands Agent Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables:
  OUTPUT_DIR          Output directory (default: ./runtime-build)
  BASE_IMAGE          Base Docker image
                      (default: nikolaik/python-nodejs:python3.12-nodejs22)
  TARGET              Build target: binary, binary-minimal, source,
                      source-minimal (default: binary)
  CLEAN_OUTPUT        Clean output directory before build (default: true)
  CUSTOM_TAGS         Comma-separated custom tags (default: python)
  OUTPUT_NAME         Custom output filename (optional)
  RUNTIME_API_URL     Runtime API URL for automatic upload (optional)
  RUNTIME_API_KEY     Runtime API key for authentication (optional)

Examples:
  python build_for_runtime_api.py
  TARGET=source python build_for_runtime_api.py
  RUNTIME_API_URL=https://api.example.com RUNTIME_API_KEY=key123 \\
    python build_for_runtime_api.py
        """,
    )

    parser.add_argument(
        "--target",
        choices=["binary", "binary-minimal", "source", "source-minimal"],
        help="Build target (overrides TARGET env var)",
    )
    parser.add_argument(
        "--output-dir", help="Output directory (overrides OUTPUT_DIR env var)"
    )
    parser.add_argument(
        "--no-upload",
        action="store_true",
        help="Skip Runtime API upload even if credentials are provided",
    )

    args = parser.parse_args()

    try:
        # Create configuration
        config = BuildConfig()

        # Override with command line arguments
        if args.target:
            config.target = args.target
        if args.output_dir:
            config.output_dir = args.output_dir

        # Create build context
        creator = BuildContextCreator(config)
        tar_path = creator.create()

        # Upload to Runtime API if configured and not disabled
        if not args.no_upload:
            client = RuntimeAPIClient(config)
            success = client.upload_and_build(tar_path)

            if not success:
                Logger.error("Runtime API upload/build failed")
                sys.exit(1)

        Logger.info("✅ Build context generation completed successfully!")

    except Exception as e:
        Logger.error(f"Build failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
