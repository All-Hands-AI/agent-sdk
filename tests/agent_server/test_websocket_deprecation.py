"""Test to ensure websocket deprecation warnings are not present."""

import warnings
from unittest.mock import patch

import pytest


def test_no_websocket_deprecation_warnings():
    """Test that starting the agent server does not produce websocket deprecation warnings."""  # noqa: E501
    # Capture all warnings
    with warnings.catch_warnings(record=True) as warning_list:
        warnings.simplefilter("always")

        # Mock uvicorn.run to avoid actually starting the server
        with patch("uvicorn.run") as mock_run:
            from openhands.agent_server.__main__ import main

            # Mock sys.argv to simulate command line arguments
            with patch("sys.argv", ["agent-server", "--port", "8005"]):
                try:
                    main()
                except SystemExit:
                    pass  # main() calls sys.exit, which is expected

            # Verify uvicorn.run was called with wsproto
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert call_args.kwargs.get("ws") == "wsproto", (
                "uvicorn should be configured to use wsproto websocket implementation"
            )

    # Check for websocket-related deprecation warnings
    websocket_deprecation_warnings = [
        w
        for w in warning_list
        if issubclass(w.category, DeprecationWarning)
        and ("websocket" in str(w.message).lower() or "ws_handler" in str(w.message))
    ]

    assert len(websocket_deprecation_warnings) == 0, (
        f"Found websocket deprecation warnings: "
        f"{[str(w.message) for w in websocket_deprecation_warnings]}"
    )


def test_wsproto_import_available():
    """Test that wsproto is available as a dependency."""
    try:
        import wsproto

        assert hasattr(wsproto, "ConnectionType"), "wsproto should be properly imported"
    except ImportError:
        pytest.fail("wsproto should be available as a dependency")


def test_uvicorn_wsproto_protocol_available():
    """Test that uvicorn can use wsproto websocket protocol."""
    try:
        from uvicorn.protocols.websockets.wsproto_impl import WSProtocol

        assert WSProtocol is not None, "WSProtocol should be available"
    except ImportError:
        pytest.fail("uvicorn wsproto protocol should be available")
