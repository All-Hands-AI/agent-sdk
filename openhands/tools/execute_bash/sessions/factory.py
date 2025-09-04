"""Factory for creating appropriate terminal sessions based on system capabilities."""

import platform
import subprocess

from openhands.sdk.logger import get_logger
from openhands.tools.execute_bash.sessions.base import TerminalSession
from openhands.tools.execute_bash.sessions.powershell import PowershellSession
from openhands.tools.execute_bash.sessions.subprocess import SubprocessBashSession
from openhands.tools.execute_bash.sessions.tmux import TmuxBashSession


logger = get_logger(__name__)


def _is_tmux_available() -> bool:
    """Check if tmux is available on the system."""
    try:
        result = subprocess.run(
            ["tmux", "-V"],
            capture_output=True,
            text=True,
            timeout=5.0,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _is_powershell_available() -> bool:
    """Check if PowerShell is available on the system."""
    if platform.system() == "Windows":
        # Check for Windows PowerShell
        powershell_cmd = "powershell"
    else:
        # Check for PowerShell Core (pwsh) on non-Windows systems
        powershell_cmd = "pwsh"

    try:
        result = subprocess.run(
            [powershell_cmd, "-Command", "Write-Host 'PowerShell Available'"],
            capture_output=True,
            text=True,
            timeout=5.0,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def create_terminal_session(
    work_dir: str,
    username: str | None = None,
    max_memory_mb: int | None = None,
    no_change_timeout_seconds: int | None = None,
    session_type: str | None = None,
) -> TerminalSession:
    """Create an appropriate terminal session based on system capabilities.

    Args:
        work_dir: Working directory for the session
        username: Optional username for the session
        max_memory_mb: Optional memory limit in MB
        no_change_timeout_seconds: Timeout for no output change
        session_type: Force a specific session type ('tmux', 'subprocess', 'powershell')
                     If None, auto-detect based on system capabilities

    Returns:
        TerminalSession instance

    Raises:
        RuntimeError: If the requested session type is not available
    """
    if session_type:
        # Force specific session type
        if session_type == "tmux":
            if not _is_tmux_available():
                raise RuntimeError("Tmux is not available on this system")
            logger.info("Using forced TmuxBashSession")
            return TmuxBashSession(
                work_dir, username, max_memory_mb, no_change_timeout_seconds
            )
        elif session_type == "subprocess":
            logger.info("Using forced SubprocessBashSession")
            return SubprocessBashSession(
                work_dir, username, max_memory_mb, no_change_timeout_seconds
            )
        elif session_type == "powershell":
            if not _is_powershell_available():
                raise RuntimeError("PowerShell is not available on this system")
            logger.info("Using forced PowershellSession")
            return PowershellSession(
                work_dir, username, max_memory_mb, no_change_timeout_seconds
            )
        else:
            raise ValueError(f"Unknown session type: {session_type}")

    # Auto-detect based on system capabilities
    system = platform.system()

    if system == "Windows":
        # On Windows, prefer PowerShell if available, otherwise use subprocess
        if _is_powershell_available():
            logger.info("Auto-detected: Using PowershellSession on Windows")
            return PowershellSession(
                work_dir, username, max_memory_mb, no_change_timeout_seconds
            )
        else:
            logger.info(
                "Auto-detected: Using SubprocessBashSession on Windows "
                "(PowerShell not available)"
            )
            return SubprocessBashSession(
                work_dir, username, max_memory_mb, no_change_timeout_seconds
            )
    else:
        # On Unix-like systems, prefer tmux if available, otherwise use subprocess
        if _is_tmux_available():
            logger.info("Auto-detected: Using TmuxBashSession (tmux available)")
            return TmuxBashSession(
                work_dir, username, max_memory_mb, no_change_timeout_seconds
            )
        else:
            logger.info(
                "Auto-detected: Using SubprocessBashSession (tmux not available)"
            )
            return SubprocessBashSession(
                work_dir, username, max_memory_mb, no_change_timeout_seconds
            )
