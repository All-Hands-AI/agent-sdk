from typing import TYPE_CHECKING, Callable, Literal

from openhands.sdk.logger import get_logger
from openhands.sdk.tool import ToolExecutor
from openhands.tools.execute_bash.definition import (
    ExecuteBashAction,
    ExecuteBashObservation,
)
from openhands.tools.execute_bash.terminal.factory import create_terminal_session


if TYPE_CHECKING:
    from openhands.sdk.conversation.secrets_manager import SecretsManager


logger = get_logger(__name__)


class BashExecutor(ToolExecutor):
    def __init__(
        self,
        working_dir: str,
        username: str | None = None,
        no_change_timeout_seconds: int | None = None,
        terminal_type: Literal["tmux", "subprocess"] | None = None,
        secrets_manager_provider: Callable[[], "SecretsManager | None"] | None = None,
    ):
        """Initialize BashExecutor with auto-detected or specified session type.

        Args:
            working_dir: Working directory for bash commands
            username: Optional username for the bash session
            no_change_timeout_seconds: Timeout for no output change
            terminal_type: Force a specific session type:
                         ('tmux', 'subprocess').
                         If None, auto-detect based on system capabilities
            secrets_manager_provider: Optional function that returns the current
                                    secrets manager for environment variable injection
        """
        self.session = create_terminal_session(
            work_dir=working_dir,
            username=username,
            no_change_timeout_seconds=no_change_timeout_seconds,
            terminal_type=terminal_type,
        )
        self.session.initialize()
        self.secrets_manager_provider = secrets_manager_provider

    def __call__(self, action: ExecuteBashAction) -> ExecuteBashObservation:
        # Check if we need to inject secrets as environment variables
        if (
            self.secrets_manager_provider
            and action.command.strip()
            and not action.is_input
        ):
            secrets_manager = self.secrets_manager_provider()
            if secrets_manager and secrets_manager.has_secrets():
                env_vars = secrets_manager.get_secrets_as_env_vars(action.command)
                if env_vars:
                    # Create export statements for the secrets
                    export_statements = []
                    for key, value in env_vars.items():
                        # Escape the secret value for bash
                        escaped_value = value.replace("'", "'\"'\"'")
                        export_statements.append(f"export {key}='{escaped_value}'")

                    # Create a modified action with export statements
                    exports = " && ".join(export_statements)
                    modified_command = f"{exports} && {action.command}"

                    logger.debug(
                        f"Injecting {len(env_vars)} secrets as environment variables"
                    )

                    # Create new action with modified command
                    modified_action = ExecuteBashAction(
                        command=modified_command,
                        is_input=action.is_input,
                        timeout=action.timeout,
                    )
                    return self.session.execute(modified_action)

        # Execute the original action if no secrets need to be injected
        return self.session.execute(action)
