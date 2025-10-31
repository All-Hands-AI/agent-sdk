"""Tests for docker build.py cache strategy."""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

from openhands.agent_server.docker.build import (
    BuildOptions,
    _active_buildx_driver,
    build,
)


def test_active_buildx_driver_docker():
    """Test detecting docker driver."""
    mock_stdout = "Driver: docker\nOther: info\n"
    with patch(
        "openhands.agent_server.docker.build._run",
        return_value=Mock(stdout=mock_stdout),
    ):
        assert _active_buildx_driver() == "docker"


def test_active_buildx_driver_docker_container():
    """Test detecting docker-container driver."""
    mock_stdout = "Driver: docker-container\nOther: info\n"
    with patch(
        "openhands.agent_server.docker.build._run",
        return_value=Mock(stdout=mock_stdout),
    ):
        assert _active_buildx_driver() == "docker-container"


def test_active_buildx_driver_error():
    """Test handling error when docker buildx inspect fails."""
    with patch(
        "openhands.agent_server.docker.build._run",
        side_effect=subprocess.CalledProcessError(1, ["docker", "buildx", "inspect"]),
    ):
        assert _active_buildx_driver() is None


def test_build_cache_strategy_push_with_docker_driver():
    """
    Test that when push=True and driver=docker, no cache-to is added.

    This is the main fix for issue #982.
    """
    mock_sdk_root = Path("/mock/sdk/root")

    opts = BuildOptions(
        base_image="test-image:latest",
        sdk_project_root=mock_sdk_root,
        image="ghcr.io/test/image",
        target="binary",
        platforms=["linux/amd64"],
        push=True,
    )

    with (
        patch(
            "openhands.agent_server.docker.build._active_buildx_driver",
            return_value="docker",
        ),
        patch(
            "openhands.agent_server.docker.build._make_build_context",
            return_value=Path("/tmp/mock-context"),
        ),
        patch("openhands.agent_server.docker.build._run") as mock_run,
        patch("pathlib.Path.exists", return_value=True),
        patch("openhands.agent_server.docker.build.logger") as mock_logger,
    ):
        mock_run.return_value = Mock(stdout="", stderr="")

        try:
            build(opts)
        except Exception:
            # We don't care about the actual build result, just the args
            pass

        # Check that _run was called with docker buildx build
        assert mock_run.called
        build_args = mock_run.call_args[0][0]

        # Verify that --cache-from is present
        assert "--cache-from" in build_args

        # Verify that --cache-to is NOT present (this is the fix)
        assert "--cache-to" not in build_args

        # Verify warning was logged
        warning_calls = [
            call
            for call in mock_logger.warning.call_args_list
            if "docker" in str(call).lower()
            and "does not support cache export" in str(call).lower()
        ]
        assert len(warning_calls) > 0


def test_build_cache_strategy_push_with_docker_container_driver():
    """Test that when push=True and driver=docker-container, cache-to is added."""
    mock_sdk_root = Path("/mock/sdk/root")

    opts = BuildOptions(
        base_image="test-image:latest",
        sdk_project_root=mock_sdk_root,
        image="ghcr.io/test/image",
        target="binary",
        platforms=["linux/amd64"],
        push=True,
    )

    with (
        patch(
            "openhands.agent_server.docker.build._active_buildx_driver",
            return_value="docker-container",
        ),
        patch(
            "openhands.agent_server.docker.build._make_build_context",
            return_value=Path("/tmp/mock-context"),
        ),
        patch("openhands.agent_server.docker.build._run") as mock_run,
        patch("pathlib.Path.exists", return_value=True),
        patch("openhands.agent_server.docker.build.logger"),
    ):
        mock_run.return_value = Mock(stdout="", stderr="")

        try:
            build(opts)
        except Exception:
            # We don't care about the actual build result, just the args
            pass

        # Check that _run was called with docker buildx build
        assert mock_run.called
        build_args = mock_run.call_args[0][0]

        # Verify that both --cache-from and --cache-to are present
        assert "--cache-from" in build_args
        assert "--cache-to" in build_args

        # Verify registry cache is used
        cache_to_idx = build_args.index("--cache-to")
        cache_to_value = build_args[cache_to_idx + 1]
        assert "type=registry" in cache_to_value


def test_build_cache_strategy_no_push_docker_driver():
    """Test that when push=False and driver=docker, inline cache is used."""
    mock_sdk_root = Path("/mock/sdk/root")

    opts = BuildOptions(
        base_image="test-image:latest",
        sdk_project_root=mock_sdk_root,
        image="test/image",
        target="binary",
        platforms=["linux/amd64"],
        push=False,
    )

    with (
        patch(
            "openhands.agent_server.docker.build._active_buildx_driver",
            return_value="docker",
        ),
        patch(
            "openhands.agent_server.docker.build._make_build_context",
            return_value=Path("/tmp/mock-context"),
        ),
        patch("openhands.agent_server.docker.build._run") as mock_run,
        patch("pathlib.Path.exists", return_value=True),
        patch("openhands.agent_server.docker.build.logger"),
    ):
        mock_run.return_value = Mock(stdout="", stderr="")

        try:
            build(opts)
        except Exception:
            # We don't care about the actual build result, just the args
            pass

        # Check that _run was called with docker buildx build
        assert mock_run.called
        build_args = mock_run.call_args[0][0]

        # Verify that inline cache is used
        assert "--build-arg" in build_args
        assert "BUILDKIT_INLINE_CACHE=1" in build_args

        # Verify no registry cache is used
        assert "--cache-to" not in build_args
