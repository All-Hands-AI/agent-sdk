from typing import Callable, Literal

from openhands.sdk.logger import get_logger
from openhands.sdk.tool import ToolExecutor
from openhands.tools.execute_bash.definition import (
    ExecuteBashAction,
    ExecuteBashObservation,
)
from openhands.tools.execute_bash.terminal.factory import create_terminal_session


logger = get_logger(__name__)


class BashExecutor(ToolExecutor):
    def __init__(
        self,
        working_dir: str,
        username: str | None = None,
        no_change_timeout_seconds: int | None = None,
        terminal_type: Literal["tmux", "subprocess"] | None = None,
        env_provider: Callable[[str], dict[str, str]] | None = None,
    ):
        """Initialize BashExecutor with auto-detected or specified session type.

        Args:
            working_dir: Working directory for bash commands
            username: Optional username for the bash session
            no_change_timeout_seconds: Timeout for no output change
            terminal_type: Force a specific session type:
                         ('tmux', 'subprocess').
                         If None, auto-detect based on system capabilities
            env_provider: Optional function mapping a command string to env vars
                          that should be exported for that command
        """
        self.session = create_terminal_session(
            work_dir=working_dir,
            username=username,
            no_change_timeout_seconds=no_change_timeout_seconds,
            terminal_type=terminal_type,
        )
        self.session.initialize()
        self.env_provider = env_provider

    def __call__(self, action: ExecuteBashAction) -> ExecuteBashObservation:
        # If env vars are needed for this command, export them as a separate action first
        if self.env_provider and action.command.strip() and not action.is_input:
            env_vars = self.env_provider(action.command)
            if env_vars:
                export_statements = []
                for key, value in env_vars.items():
                    escaped_value = value.replace("'", "'\"'\"'")
                    export_statements.append(f"export {key}='{escaped_value}'")
                exports_cmd = " && ".join(export_statements)

                logger.debug(
                    f"Exporting {len(env_vars)} environment variables before command"
                )

                # Execute the export command separately to persist env in the session
                _ = self.session.execute(
                    ExecuteBashAction(
                        command=exports_cmd,
                        is_input=False,
                        timeout=action.timeout,
                    )
                )

        # Now execute the original action unchanged
        return self.session.execute(action)
