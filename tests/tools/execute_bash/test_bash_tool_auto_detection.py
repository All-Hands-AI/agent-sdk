"""Tests for BashTool auto-detection functionality."""

import tempfile
from unittest.mock import patch

from openhands.tools.execute_bash import BashTool
from openhands.tools.execute_bash.definition import ExecuteBashAction
from openhands.tools.execute_bash.sessions.powershell import PowershellSession
from openhands.tools.execute_bash.sessions.subprocess import SubprocessBashSession
from openhands.tools.execute_bash.sessions.tmux import TmuxBashSession


class TestBashToolAutoDetection:
    """Test BashTool auto-detection functionality."""

    def test_default_auto_detection(self):
        """Test that BashTool auto-detects the appropriate session type."""
        with tempfile.TemporaryDirectory() as temp_dir:
            tool = BashTool(working_dir=temp_dir)

            # Should auto-detect based on system capabilities
            session_type = type(tool.executor.session).__name__
            assert session_type in [
                "TmuxBashSession",
                "SubprocessBashSession",
                "PowershellSession",
            ]

            # Test that it works
            action = ExecuteBashAction(
                command="echo 'Auto-detection test'", security_risk="LOW"
            )
            obs = tool.executor(action)
            assert "Auto-detection test" in obs.output

    def test_forced_session_types(self):
        """Test forcing specific session types."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test forced subprocess session
            tool = BashTool(working_dir=temp_dir, session_type="subprocess")
            assert isinstance(tool.executor.session, SubprocessBashSession)

            # Test basic functionality
            action = ExecuteBashAction(
                command="echo 'Subprocess test'", security_risk="LOW"
            )
            obs = tool.executor(action)
            assert "Subprocess test" in obs.output

    @patch("platform.system")
    def test_windows_auto_detection(self, mock_system):
        """Test auto-detection behavior on Windows."""
        mock_system.return_value = "Windows"

        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock PowerShell as available
            with (
                patch(
                    "openhands.tools.execute_bash.sessions.factory._is_powershell_available",
                    return_value=True,
                ),
                patch("subprocess.run") as mock_run,
            ):
                # Mock successful PowerShell initialization
                mock_run.return_value.returncode = 0
                tool = BashTool(working_dir=temp_dir)
                assert isinstance(tool.executor.session, PowershellSession)

            # Mock PowerShell as unavailable
            with patch(
                "openhands.tools.execute_bash.sessions.factory._is_powershell_available",
                return_value=False,
            ):
                tool = BashTool(working_dir=temp_dir)
                assert isinstance(tool.executor.session, SubprocessBashSession)

    @patch("platform.system")
    def test_unix_auto_detection(self, mock_system):
        """Test auto-detection behavior on Unix-like systems."""
        mock_system.return_value = "Linux"

        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock tmux as available
            with patch(
                "openhands.tools.execute_bash.sessions.factory._is_tmux_available",
                return_value=True,
            ):
                tool = BashTool(working_dir=temp_dir)
                assert isinstance(tool.executor.session, TmuxBashSession)

            # Mock tmux as unavailable
            with patch(
                "openhands.tools.execute_bash.sessions.factory._is_tmux_available",
                return_value=False,
            ):
                tool = BashTool(working_dir=temp_dir)
                assert isinstance(tool.executor.session, SubprocessBashSession)

    def test_session_parameters(self):
        """Test that session parameters are properly passed."""
        with tempfile.TemporaryDirectory() as temp_dir:
            tool = BashTool(
                working_dir=temp_dir,
                username="testuser",
                max_memory_mb=1024,
                no_change_timeout_seconds=60,
                session_type="subprocess",
            )

            session = tool.executor.session
            assert session.work_dir == temp_dir
            assert session.username == "testuser"
            assert session.max_memory_mb == 1024
            assert session.no_change_timeout_seconds == 60

    def test_backward_compatibility(self):
        """Test that the simplified API still works."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # This should work just like before
            tool = BashTool(working_dir=temp_dir)

            action = ExecuteBashAction(
                command="echo 'Backward compatibility test'", security_risk="LOW"
            )
            obs = tool.executor(action)
            assert "Backward compatibility test" in obs.output
            assert obs.metadata.exit_code == 0

    def test_tool_metadata(self):
        """Test that tool metadata is preserved."""
        with tempfile.TemporaryDirectory() as temp_dir:
            tool = BashTool(working_dir=temp_dir)

            assert tool.name == "execute_bash"
            assert tool.description is not None
            assert tool.action_type == ExecuteBashAction
            assert hasattr(tool, "annotations")

    def test_session_lifecycle(self):
        """Test session lifecycle management."""
        with tempfile.TemporaryDirectory() as temp_dir:
            tool = BashTool(working_dir=temp_dir, session_type="subprocess")

            # Session should be initialized
            assert tool.executor.session._initialized

            # Should be able to execute commands
            action = ExecuteBashAction(
                command="echo 'Lifecycle test'", security_risk="LOW"
            )
            obs = tool.executor(action)
            assert "Lifecycle test" in obs.output

            # Manual cleanup should work
            tool.executor.session.close()
            assert tool.executor.session._closed
