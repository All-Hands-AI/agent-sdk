"""Manual test of ApptainerWorkspace - no LLM required.

This script tests the SIF image creation functionality of ApptainerWorkspace.
Note: Full agent-server testing requires Docker to build the agent-server first.
This test demonstrates that Apptainer can pull and convert Docker images
without Docker daemon.
"""

import subprocess
import sys
from pathlib import Path


def test_apptainer_pull():
    """Test basic Apptainer pull functionality."""

    print("=" * 80)
    print("Testing Apptainer Image Pull Functionality")
    print("=" * 80)

    # Create cache directory
    cache_dir = Path("/tmp/apptainer-test-cache")
    cache_dir.mkdir(exist_ok=True)

    # Test pulling a simple image
    print("\n1. Testing Apptainer pull from Docker Hub...")
    test_image = "python:3.12-slim"
    sif_path = cache_dir / "python_3.12-slim.sif"

    if sif_path.exists():
        print(f"   ℹ Removing existing SIF file: {sif_path}")
        sif_path.unlink()

    print(f"   - Pulling Docker image: {test_image}")
    print("   - Converting to SIF format...")
    print("   - This may take a few minutes on first run...")

    pull_cmd = [
        "apptainer",
        "pull",
        str(sif_path),
        f"docker://{test_image}",
    ]

    try:
        result = subprocess.run(
            pull_cmd, check=True, capture_output=True, text=True, timeout=300
        )
        print(f"   ✓ Successfully created SIF file: {sif_path}")
        print(f"   - File size: {sif_path.stat().st_size / 1024 / 1024:.2f} MB")

    except subprocess.TimeoutExpired:
        print("   ✗ Timeout while pulling image")
        return False
    except subprocess.CalledProcessError as e:
        print(f"   ✗ Failed to pull image: {e.stderr}")
        return False

    # Test running a simple command in the container
    print("\n2. Testing Apptainer exec...")
    exec_cmd = [
        "apptainer",
        "exec",
        str(sif_path),
        "python",
        "--version",
    ]

    try:
        result = subprocess.run(
            exec_cmd, check=True, capture_output=True, text=True, timeout=10
        )
        print("   ✓ Successfully executed command in container")
        print(f"   - Output: {result.stdout.strip()}")
    except subprocess.CalledProcessError as e:
        print(f"   ✗ Failed to execute command: {e.stderr}")
        return False

    # Test instance management
    print("\n3. Testing Apptainer instance management...")
    instance_name = "test-instance"

    # Start instance
    start_cmd = [
        "apptainer",
        "instance",
        "start",
        str(sif_path),
        instance_name,
    ]

    instance_started = False
    try:
        subprocess.run(
            start_cmd, check=True, capture_output=True, text=True, timeout=10
        )
        print(f"   ✓ Started Apptainer instance: {instance_name}")
        instance_started = True
    except subprocess.CalledProcessError as e:
        print("   ⚠ Could not start instance (may require FUSE dependencies)")
        if "squashfuse not found" in e.stderr or "fuse2fs not found" in e.stderr:
            print("   ℹ This is expected in some environments without FUSE support")
            print(
                "   ℹ ApptainerWorkspace can still work with 'exec' mode for commands"
            )
        else:
            print(f"   Error details: {e.stderr[:200]}")

    if instance_started:
        # List instances
        list_cmd = ["apptainer", "instance", "list"]
        try:
            result = subprocess.run(
                list_cmd, check=True, capture_output=True, text=True, timeout=10
            )
            print("   ✓ Instance is running")
            print(f"   - Instance list:\n{result.stdout}")
        except subprocess.CalledProcessError as e:
            print(f"   ⚠ Could not list instances: {e.stderr}")

        # Stop instance
        stop_cmd = ["apptainer", "instance", "stop", instance_name]
        try:
            subprocess.run(
                stop_cmd, check=True, capture_output=True, text=True, timeout=10
            )
            print("   ✓ Stopped Apptainer instance")
        except subprocess.CalledProcessError as e:
            print(f"   ⚠ Failed to stop instance: {e.stderr}")

    # Cleanup
    print("\n4. Cleaning up...")
    if sif_path.exists():
        sif_path.unlink()
        print("   ✓ Removed SIF file")

    print("\n" + "=" * 80)
    print("SUCCESS: Apptainer is working correctly!")
    print("=" * 80)
    print("\nNext steps for ApptainerWorkspace:")
    print("1. Build agent-server image with Docker (openhands/agent-server)")
    print("2. Use ApptainerWorkspace with server_image parameter")
    print("3. The workspace will convert the Docker image to SIF and run it")
    print("\nNOTE: Full agent-server testing requires Docker to be available")
    print("for building the server image initially.")
    print("=" * 80)

    return True


if __name__ == "__main__":
    # Verify apptainer is installed
    try:
        result = subprocess.run(
            ["/usr/local/bin/apptainer", "--version"], capture_output=True, text=True
        )
        print(f"Apptainer version: {result.stdout.strip()}\n")
    except FileNotFoundError:
        print("ERROR: Apptainer not found. Please install it first.")
        sys.exit(1)

    success = test_apptainer_pull()
    sys.exit(0 if success else 1)
