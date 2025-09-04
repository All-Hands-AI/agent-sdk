"""Tests for session factory and auto-detection logic."""

import tempfile
from unittest.mock import patch

import pytest

from openhands.tools.execute_bash.terminal import (
    PowershellTerminal,
    SubprocessTerminal,
    TerminalSession,
    TmuxTerminal,
)
from openhands.tools.execute_bash.terminal.factory import (
    _is_powershell_available,
    _is_tmux_available,
    create_terminal_session,
)


class TestSessionFactory:
    """Test session factory functionality."""

    def test_tmux_detection(self):
        """Test tmux availability detection."""
        # This will depend on the test environment
        result = _is_tmux_available()
        assert isinstance(result, bool)

    def test_powershell_detection(self):
        """Test PowerShell availability detection."""
        result = _is_powershell_available()
        assert isinstance(result, bool)

    def test_forced_session_types(self):
        """Test forcing specific session types."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test forced subprocess session
            session = create_terminal_session(
                work_dir=temp_dir, session_type="subprocess"
            )
            assert isinstance(session, TerminalSession)
            assert isinstance(session.terminal, SubprocessTerminal)
            session.close()

            # Test forced tmux session (if available)
            if _is_tmux_available():
                session = create_terminal_session(
                    work_dir=temp_dir, session_type="tmux"
                )
                assert isinstance(session, TerminalSession)
                assert isinstance(session.terminal, TmuxTerminal)
                session.close()

            # Test forced PowerShell session (if available)
            if _is_powershell_available():
                session = create_terminal_session(
                    work_dir=temp_dir, session_type="powershell"
                )
                assert isinstance(session, TerminalSession)
                assert isinstance(session.terminal, PowershellTerminal)
                session.close()

    def test_invalid_session_type(self):
        """Test error handling for invalid session types."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with pytest.raises(ValueError, match="Unknown session type"):
                create_terminal_session(work_dir=temp_dir, session_type="invalid")

    def test_unavailable_session_type(self):
        """Test error handling when requested session type is unavailable."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock tmux as unavailable
            with patch(
                "openhands.tools.execute_bash.sessions.factory._is_tmux_available",
                return_value=False,
            ):
                with pytest.raises(RuntimeError, match="Tmux is not available"):
                    create_terminal_session(work_dir=temp_dir, session_type="tmux")

            # Mock PowerShell as unavailable
            with patch(
                "openhands.tools.execute_bash.sessions.factory._is_powershell_available",
                return_value=False,
            ):
                with pytest.raises(RuntimeError, match="PowerShell is not available"):
                    create_terminal_session(
                        work_dir=temp_dir, session_type="powershell"
                    )

    @patch("platform.system")
    def test_auto_detection_windows(self, mock_system):
        """Test auto-detection on Windows."""
        mock_system.return_value = "Windows"

        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock PowerShell as available
            with patch(
                "openhands.tools.execute_bash.sessions.factory._is_powershell_available",
                return_value=True,
            ):
                session = create_terminal_session(work_dir=temp_dir)
                assert isinstance(session, TerminalSession)
                assert isinstance(session.terminal, PowershellTerminal)
                session.close()

            # Mock PowerShell as unavailable
            with patch(
                "openhands.tools.execute_bash.sessions.factory._is_powershell_available",
                return_value=False,
            ):
                session = create_terminal_session(work_dir=temp_dir)
                assert isinstance(session, TerminalSession)
                assert isinstance(session.terminal, SubprocessTerminal)
                session.close()

    @patch("platform.system")
    def test_auto_detection_unix(self, mock_system):
        """Test auto-detection on Unix-like systems."""
        mock_system.return_value = "Linux"

        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock tmux as available
            with patch(
                "openhands.tools.execute_bash.sessions.factory._is_tmux_available",
                return_value=True,
            ):
                session = create_terminal_session(work_dir=temp_dir)
                assert isinstance(session, TerminalSession)
                assert isinstance(session.terminal, TmuxTerminal)
                session.close()

            # Mock tmux as unavailable
            with patch(
                "openhands.tools.execute_bash.sessions.factory._is_tmux_available",
                return_value=False,
            ):
                session = create_terminal_session(work_dir=temp_dir)
                assert isinstance(session, TerminalSession)
                assert isinstance(session.terminal, SubprocessTerminal)
                session.close()

    def test_session_parameters_passed(self):
        """Test that session parameters are properly passed."""
        with tempfile.TemporaryDirectory() as temp_dir:
            session = create_terminal_session(
                work_dir=temp_dir,
                username="testuser",
                no_change_timeout_seconds=60,
                session_type="subprocess",
            )

            assert isinstance(session, TerminalSession)
            assert session.work_dir == temp_dir
            assert session.username == "testuser"
            assert session.no_change_timeout_seconds == 60
            # Check terminal parameters too
            assert session.terminal.work_dir == temp_dir
            assert session.terminal.username == "testuser"
            session.close()
