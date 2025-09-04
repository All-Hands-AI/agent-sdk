"""Backward compatibility wrapper for BashSession.

This module maintains backward compatibility by providing the original BashSession
class that now delegates to TmuxBashSession.
"""

from openhands.tools.execute_bash.base_terminal import TerminalCommandStatus
from openhands.tools.execute_bash.tmux_session import TmuxBashSession


# Backward compatibility alias - just use the same enum
BashCommandStatus = TerminalCommandStatus


class BashSession(TmuxBashSession):
    """Backward compatibility wrapper for TmuxBashSession.

    This class maintains the original BashSession interface while delegating
    to the new TmuxBashSession implementation.
    """

    pass
