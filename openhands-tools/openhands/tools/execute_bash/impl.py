from collections.abc import Callable
from typing import Literal

from openhands.sdk.logger import get_logger
from openhands.sdk.tool import ToolExecutor
from openhands.tools.execute_bash.definition import (
    ExecuteBashAction,
    ExecuteBashObservation,
)
from openhands.tools.execute_bash.terminal.factory import create_terminal_session
from openhands.tools.execute_bash.terminal.terminal_session import TerminalSession


logger = get_logger(__name__)


class BashExecutor(ToolExecutor[ExecuteBashAction, ExecuteBashObservation]):
    session: TerminalSession
    env_masker: Callable[[str], str] | None

    def __init__(
        self,
        working_dir: str,
        username: str | None = None,
        no_change_timeout_seconds: int | None = None,
        terminal_type: Literal["tmux", "subprocess"] | None = None,
        env_masker: Callable[[str], str] | None = None,
    ):
        """Initialize BashExecutor with auto-detected or specified session type.

        Args:
            working_dir: Working directory for bash commands
            username: Optional username for the bash session
            no_change_timeout_seconds: Timeout for no output change
            terminal_type: Force a specific session type:
                         ('tmux', 'subprocess').
                         If None, auto-detect based on system capabilities
            env_masker: Optional function that masks secret values in output.
        """
        self.session = create_terminal_session(
            work_dir=working_dir,
            username=username,
            no_change_timeout_seconds=no_change_timeout_seconds,
            terminal_type=terminal_type,
        )
        self.session.initialize()
        self.env_masker = env_masker
        logger.info(
            f"BashExecutor initialized with working_dir: {working_dir}, "
            f"username: {username}, "
            f"terminal_type: {terminal_type or self.session.__class__.__name__}"
        )

    def reset(self) -> ExecuteBashObservation:
        """Reset the terminal session by creating a new instance.

        Returns:
            ExecuteBashObservation with reset confirmation message
        """
        original_work_dir = self.session.work_dir
        original_username = self.session.username
        original_no_change_timeout = self.session.no_change_timeout_seconds

        self.session.close()
        self.session = create_terminal_session(
            work_dir=original_work_dir,
            username=original_username,
            no_change_timeout_seconds=original_no_change_timeout,
            terminal_type=None,  # Let it auto-detect like before
        )
        self.session.initialize()

        logger.info(
            f"Terminal session reset successfully with working_dir: {original_work_dir}"
        )

        return ExecuteBashObservation(
            output=(
                "Terminal session has been reset. All previous environment "
                "variables and session state have been cleared."
            ),
            command="[RESET]",
            exit_code=0,
        )

    def __call__(self, action: ExecuteBashAction) -> ExecuteBashObservation:
        # Validate field combinations
        if action.reset and action.is_input:
            raise ValueError("Cannot use reset=True with is_input=True")

        if action.reset:
            reset_result = self.reset()

            # Handle command execution after reset
            if action.command.strip():
                command_action = ExecuteBashAction(
                    command=action.command,
                    timeout=action.timeout,
                    is_input=False,  # is_input validated to be False when reset=True
                )
                command_result = self.session.execute(command_action)
                observation = command_result.model_copy(
                    update={
                        "output": (
                            reset_result.output + "\n\n" + command_result.output
                        ),
                        "command": f"[RESET] {action.command}",
                    }
                )
            else:
                # Reset only, no command to execute
                observation = reset_result
        else:
            observation = self.session.execute(action)

        # Apply automatic secrets masking using env_masker
        if self.env_masker and observation.output:
            masked_output = self.env_masker(observation.output)
            data = observation.model_dump(exclude={"output"})
            return ExecuteBashObservation(**data, output=masked_output)

        return observation

    def close(self) -> None:
        """Close the terminal session and clean up resources."""
        if hasattr(self, "session"):
            self.session.close()
