"""
Tests for proper handling of Python shutdown in terminal sessions.

This test suite verifies that terminal sessions handle Python shutdown gracefully
without raising ImportError exceptions during cleanup.
"""

import sys
import tempfile
from unittest.mock import Mock, patch

import pytest

from openhands.tools.execute_bash.terminal.interface import TerminalSessionBase
from openhands.tools.execute_bash.terminal.tmux_terminal import TmuxTerminal


def test_terminal_session_base_del_during_shutdown():
    """Test that TerminalSessionBase.__del__ handles Python shutdown gracefully."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a mock terminal to avoid tmux dependency
        mock_terminal = Mock()
        mock_terminal.work_dir = temp_dir
        mock_terminal.username = None
        mock_terminal.close = Mock()
        
        # Create a terminal session with the mock terminal
        from openhands.tools.execute_bash.terminal.terminal_session import TerminalSession
        session = TerminalSession(mock_terminal)
        session._initialized = True
        
        # Simulate Python shutdown by setting sys.meta_path to None
        with patch.object(sys, 'meta_path', None):
            # This should not raise an ImportError
            try:
                session.__del__()
            except ImportError as e:
                if "sys.meta_path is None" in str(e):
                    pytest.fail(f"ImportError during shutdown: {e}")
                else:
                    # Re-raise if it's a different ImportError
                    raise
        
        # Verify that close was not called during shutdown
        mock_terminal.close.assert_not_called()


def test_tmux_terminal_close_during_shutdown():
    """Test that TmuxTerminal.close() handles Python shutdown gracefully."""
    with tempfile.TemporaryDirectory() as temp_dir:
        terminal = TmuxTerminal(work_dir=temp_dir)
        
        # Mock the session to avoid actual tmux initialization
        mock_session = Mock()
        mock_session.kill = Mock()
        terminal.session = mock_session
        terminal._initialized = True
        
        # Simulate Python shutdown by setting sys.meta_path to None
        with patch.object(sys, 'meta_path', None):
            # This should not raise an ImportError
            try:
                terminal.close()
            except ImportError as e:
                if "sys.meta_path is None" in str(e):
                    pytest.fail(f"ImportError during shutdown: {e}")
                else:
                    # Re-raise if it's a different ImportError
                    raise
        
        # Verify that the terminal is marked as closed
        assert terminal.closed
        # Verify that session.kill was not called during shutdown
        mock_session.kill.assert_not_called()


def test_normal_cleanup_still_works():
    """Test that normal cleanup operations still work when not shutting down."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a mock terminal to avoid tmux dependency
        mock_terminal = Mock()
        mock_terminal.work_dir = temp_dir
        mock_terminal.username = None
        mock_terminal.close = Mock()
        
        # Create a terminal session with the mock terminal
        from openhands.tools.execute_bash.terminal.terminal_session import TerminalSession
        session = TerminalSession(mock_terminal)
        session._initialized = True
        
        # Ensure sys.meta_path is not None (normal operation)
        assert sys.meta_path is not None
        
        # Normal cleanup should work fine
        session.close()
        assert session._closed
        mock_terminal.close.assert_called_once()
        
        # Reset the mock for the next test
        mock_terminal.close.reset_mock()
        
        # __del__ should also work fine in normal conditions
        session2 = TerminalSession(mock_terminal)
        session2._initialized = True
        session2.__del__()
        assert session2._closed
        mock_terminal.close.assert_called_once()


def test_tmux_terminal_normal_cleanup_still_works():
    """Test that TmuxTerminal normal cleanup operations still work when not shutting down."""
    with tempfile.TemporaryDirectory() as temp_dir:
        terminal = TmuxTerminal(work_dir=temp_dir)
        
        # Mock the session to avoid actual tmux initialization
        mock_session = Mock()
        mock_session.kill = Mock()
        terminal.session = mock_session
        terminal._initialized = True
        
        # Ensure sys.meta_path is not None (normal operation)
        assert sys.meta_path is not None
        
        # Normal cleanup should work fine
        terminal.close()
        assert terminal.closed
        mock_session.kill.assert_called_once()


def test_multiple_close_calls_during_shutdown():
    """Test that multiple close calls during shutdown don't cause issues."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a mock terminal to avoid tmux dependency
        mock_terminal = Mock()
        mock_terminal.work_dir = temp_dir
        mock_terminal.username = None
        mock_terminal.close = Mock()
        
        # Create a terminal session with the mock terminal
        from openhands.tools.execute_bash.terminal.terminal_session import TerminalSession
        session = TerminalSession(mock_terminal)
        session._initialized = True
        
        # Simulate Python shutdown by setting sys.meta_path to None
        with patch.object(sys, 'meta_path', None):
            # Multiple __del__ calls should not raise ImportError
            try:
                session.__del__()  # First __del__ call
                session.__del__()  # Second __del__ call should be safe
            except ImportError as e:
                if "sys.meta_path is None" in str(e):
                    pytest.fail(f"ImportError during shutdown: {e}")
                else:
                    # Re-raise if it's a different ImportError
                    raise
        
        # During shutdown, we skip cleanup so _closed remains False
        # This is correct behavior - we didn't actually clean up
        assert not session._closed
        # Verify that close was not called during shutdown (only __del__ was called)
        mock_terminal.close.assert_not_called()


def test_shutdown_detection_with_sys_meta_path_none():
    """Test that sys.meta_path None is properly detected as shutdown condition."""
    with tempfile.TemporaryDirectory() as temp_dir:
        terminal = TmuxTerminal(work_dir=temp_dir)
        
        # Mock the session to avoid actual tmux initialization
        mock_session = Mock()
        mock_session.kill = Mock()
        terminal.session = mock_session
        terminal._initialized = True
        
        # Test with sys.meta_path as None (shutdown condition)
        with patch.object(sys, 'meta_path', None):
            terminal.close()
            # session.kill should not be called during shutdown
            mock_session.kill.assert_not_called()
        
        # Test with sys.meta_path as normal list (normal condition)
        mock_session.kill.reset_mock()
        terminal._closed = False  # Reset closed state
        with patch.object(sys, 'meta_path', []):
            terminal.close()
            # session.kill should be called during normal operation
            mock_session.kill.assert_called_once()