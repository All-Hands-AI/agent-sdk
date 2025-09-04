# Terminal session implementations

# Base classes and factory
from openhands.tools.execute_bash.sessions.base import (
    TerminalCommandStatus,
    TerminalSession,
)

# Backward compatibility
from openhands.tools.execute_bash.sessions.bash import BashCommandStatus, BashSession
from openhands.tools.execute_bash.sessions.factory import create_terminal_session

# Legacy session implementations (for backward compatibility)
from openhands.tools.execute_bash.sessions.powershell import PowershellSession
from openhands.tools.execute_bash.sessions.powershell_terminal import PowershellTerminal
from openhands.tools.execute_bash.sessions.subprocess import SubprocessBashSession
from openhands.tools.execute_bash.sessions.subprocess_terminal import SubprocessTerminal

# Terminal interface and backends
from openhands.tools.execute_bash.sessions.terminal_interface import TerminalInterface
from openhands.tools.execute_bash.sessions.tmux import TmuxBashSession
from openhands.tools.execute_bash.sessions.tmux_terminal import TmuxTerminal

# Unified session
from openhands.tools.execute_bash.sessions.unified_session import UnifiedBashSession


__all__ = [
    # === Base Classes and Factory ===
    "TerminalSession",
    "TerminalCommandStatus",
    "create_terminal_session",
    # === Terminal Interface and Backends ===
    "TerminalInterface",
    "TmuxTerminal",
    "SubprocessTerminal",
    "PowershellTerminal",
    # === Unified Session ===
    "UnifiedBashSession",
    # === Legacy Session Implementations ===
    "TmuxBashSession",
    "SubprocessBashSession",
    "PowershellSession",
    # === Backward Compatibility ===
    "BashSession",
    "BashCommandStatus",
]
