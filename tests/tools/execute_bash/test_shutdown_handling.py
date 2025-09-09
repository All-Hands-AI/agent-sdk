"""Tests for shutdown handling in terminal sessions.

This module tests the shutdown handling logic that prevents ImportError
during Python shutdown when terminal sessions are being cleaned up.
"""

import sys
from unittest.mock import Mock, patch

from openhands.tools.execute_bash.definition import ExecuteBashObservation
from openhands.tools.execute_bash.terminal.interface import TerminalSessionBase
from openhands.tools.execute_bash.terminal.tmux_terminal import TmuxTerminal


class MockTerminalSession(TerminalSessionBase):
    """Mock terminal session for testing."""

    def __init__(self, work_dir: str, username: str | None = None):
        super().__init__(work_dir, username)
        self.close_called = False

    def initialize(self) -> None:
        """Mock initialize method."""
        self._initialized = True

    def execute(self, action) -> ExecuteBashObservation:
        """Mock execute method."""
        return ExecuteBashObservation(
            command=action.command, exit_code=0, output="mock output"
        )

    def close(self) -> None:
        """Mock close method."""
        self.close_called = True
        self._closed = True

    def interrupt(self) -> bool:
        """Mock interrupt method."""
        return True

    def is_running(self) -> bool:
        """Mock is_running method."""
        return False


def test_terminal_session_del_normal_operation():
    """Test that __del__ calls close() during normal operation."""
    session = MockTerminalSession("/tmp")
    session.initialize()

    # Simulate normal __del__ call
    session.__del__()

    assert session.close_called


def test_terminal_session_del_during_shutdown():
    """Test that __del__ skips close() during Python shutdown."""
    session = MockTerminalSession("/tmp")
    session.initialize()

    # Simulate Python shutdown by setting sys.meta_path to None
    with patch.object(sys, "meta_path", None):
        session.__del__()

    # close() should not have been called during shutdown
    assert not session.close_called


def test_terminal_session_del_multiple_calls():
    """Test that multiple __del__ calls are safe."""
    session = MockTerminalSession("/tmp")
    session.initialize()

    # First call should work
    session.__del__()
    assert session.close_called

    # Reset for second test
    session.close_called = False

    # Second call should also be safe
    session.__del__()
    # close() might be called again, but it should be safe


def test_tmux_terminal_close_normal_operation():
    """Test that TmuxTerminal.close() works normally."""
    terminal = TmuxTerminal("/tmp")

    # Manually set up a mock session to avoid complex initialization
    mock_session = Mock()
    terminal.session = mock_session

    # Normal close should call session.kill()
    terminal.close()

    mock_session.kill.assert_called_once()
    assert terminal.closed


def test_tmux_terminal_close_during_shutdown():
    """Test that TmuxTerminal.close() skips session.kill() during shutdown."""
    terminal = TmuxTerminal("/tmp")

    # Manually set up a mock session to avoid complex initialization
    mock_session = Mock()
    terminal.session = mock_session

    # Simulate Python shutdown
    with patch.object(sys, "meta_path", None):
        terminal.close()

    # session.kill() should not have been called during shutdown
    mock_session.kill.assert_not_called()
    assert terminal.closed


def test_tmux_terminal_close_multiple_calls():
    """Test that multiple close() calls are safe."""
    terminal = TmuxTerminal("/tmp")

    # Manually set up a mock session to avoid complex initialization
    mock_session = Mock()
    terminal.session = mock_session

    # First close
    terminal.close()
    mock_session.kill.assert_called_once()

    # Second close should be safe and not call kill() again
    terminal.close()
    mock_session.kill.assert_called_once()  # Still only called once
