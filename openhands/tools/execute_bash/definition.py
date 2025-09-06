"""Execute bash tool implementation."""

# Import for type annotation
from typing import TYPE_CHECKING, Literal

from pydantic import Field

from openhands.sdk.llm import ImageContent, TextContent
from openhands.sdk.tool import ActionBase, ObservationBase, Tool, ToolAnnotations
from openhands.sdk.utils import maybe_truncate
from openhands.tools.execute_bash.constants import (
    MAX_CMD_OUTPUT_SIZE,
    NO_CHANGE_TIMEOUT_SECONDS,
)
from openhands.tools.execute_bash.metadata import CmdOutputMetadata


if TYPE_CHECKING:
    from .impl import BashExecutor


class ExecuteBashAction(ActionBase):
    """Schema for bash command execution."""

    command: str = Field(
        description="The bash command to execute. Can be empty string to view additional logs when previous exit code is `-1`. Can be `C-c` (Ctrl+C) to interrupt the currently running process. Note: You can only execute one bash command at a time. If you need to run multiple commands sequentially, you can use `&&` or `;` to chain them together."  # noqa
    )
    is_input: bool = Field(
        default=False,
        description="If True, the command is an input to the running process. If False, the command is a bash command to be executed in the terminal. Default is False.",  # noqa
    )
    timeout: float | None = Field(
        default=None,
        description=f"Optional. Sets a maximum time limit (in seconds) for running the command. If the command takes longer than this limit, you’ll be asked whether to continue or stop it. If you don’t set a value, the command will instead pause and ask for confirmation when it produces no new output for {NO_CHANGE_TIMEOUT_SECONDS} seconds. Use a higher value if the command is expected to take a long time (like installation or testing), or if it has a known fixed duration (like sleep).",  # noqa
    )


class ExecuteBashObservation(ObservationBase):
    """A ToolResult that can be rendered as a CLI output."""

    output: str = Field(description="The raw output from the tool.")
    command: str | None = Field(
        default=None,
        description="The bash command that was executed. Can be empty string if the observation is from a previous command that hit soft timeout and is not yet finished.",  # noqa
    )
    exit_code: int | None = Field(
        default=None,
        description="The exit code of the command. -1 indicates the process hit the soft timeout and is not yet finished.",  # noqa
    )
    error: bool = Field(
        default=False,
        description="Whether there was an error during command execution.",
    )
    timeout: bool = Field(
        default=False, description="Whether the command execution timed out."
    )
    metadata: CmdOutputMetadata = Field(
        default_factory=CmdOutputMetadata,
        description="Additional metadata captured from PS1 after command execution.",
    )

    @property
    def command_id(self) -> int | None:
        """Get the command ID from metadata."""
        return self.metadata.pid

    @property
    def agent_observation(self) -> list[TextContent | ImageContent]:
        ret = f"{self.metadata.prefix}{self.output}{self.metadata.suffix}"
        if self.metadata.working_dir:
            ret += f"\n[Current working directory: {self.metadata.working_dir}]"
        if self.metadata.py_interpreter_path:
            ret += f"\n[Python interpreter: {self.metadata.py_interpreter_path}]"
        if self.metadata.exit_code != -1:
            ret += f"\n[Command finished with exit code {self.metadata.exit_code}]"
        if self.error:
            ret = f"[There was an error during command execution.]\n{ret}"
        return [TextContent(text=maybe_truncate(ret, MAX_CMD_OUTPUT_SIZE))]


TOOL_DESCRIPTION = """Execute a bash command in the terminal within a persistent shell session.


### Command Execution
* One command at a time: You can only execute one bash command at a time. If you need to run multiple commands sequentially, use `&&` or `;` to chain them together.
* Persistent session: Commands execute in a persistent shell session where environment variables, virtual environments, and working directory persist between commands.
* Soft timeout: Commands have a soft timeout of 10 seconds, once that's reached, you have the option to continue or interrupt the command (see section below for details)
* Shell options: Do NOT use `set -e`, `set -eu`, or `set -euo pipefail` in shell scripts or commands in this environment. The runtime may not support them and can cause unusable shell sessions. If you want to run multi-line bash commands, write the commands to a file and then run it, instead.

### Long-running Commands
* For commands that may run indefinitely, run them in the background and redirect output to a file, e.g. `python3 app.py > server.log 2>&1 &`.
* For commands that may run for a long time (e.g. installation or testing commands), or commands that run for a fixed amount of time (e.g. sleep), you should set the "timeout" parameter of your function call to an appropriate value.
* If a bash command returns exit code `-1`, this means the process hit the soft timeout and is not yet finished. By setting `is_input` to `true`, you can:
  - Send empty `command` to retrieve additional logs
  - Send text (set `command` to the text) to STDIN of the running process
  - Send control commands like `C-c` (Ctrl+C), `C-d` (Ctrl+D), or `C-z` (Ctrl+Z) to interrupt the process
  - If you do C-c, you can re-start the process with a longer "timeout" parameter to let it run to completion

### Best Practices
* Directory verification: Before creating new directories or files, first verify the parent directory exists and is the correct location.
* Directory management: Try to maintain working directory by using absolute paths and avoiding excessive use of `cd`.

### Output Handling
* Output truncation: If the output exceeds a maximum length, it will be truncated before being returned.
"""  # noqa


execute_bash_tool = Tool(
    name="execute_bash",
    input_schema=ExecuteBashAction,
    output_schema=ExecuteBashObservation,
    description=TOOL_DESCRIPTION,
    annotations=ToolAnnotations(
        title="execute_bash",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=True,
    ),
)


class BashTool(Tool[ExecuteBashAction, ExecuteBashObservation]):
    """A Tool subclass that automatically initializes a BashExecutor with auto-detection."""  # noqa: E501

    executor: "BashExecutor"

    def __init__(
        self,
        working_dir: str,
        username: str | None = None,
        no_change_timeout_seconds: int | None = None,
        terminal_type: Literal["tmux", "subprocess"] | None = None,
    ):
        """Initialize BashTool with executor parameters.

        Args:
            working_dir: The working directory for bash commands
            username: Optional username for the bash session
            no_change_timeout_seconds: Timeout for no output change
            terminal_type: Force a specific session type:
                         ('tmux', 'subprocess').
                         If None, auto-detect based on system capabilities:
                         - On Windows: PowerShell if available, otherwise subprocess
                         - On Unix-like: tmux if available, otherwise subprocess
        """
        # Import here to avoid circular imports
        from openhands.tools.execute_bash.impl import BashExecutor

        # Initialize the executor
        executor = BashExecutor(
            working_dir=working_dir,
            username=username,
            no_change_timeout_seconds=no_change_timeout_seconds,
            terminal_type=terminal_type,
        )

        # Initialize the parent Tool with the executor
        super().__init__(
            name=execute_bash_tool.name,
            description=TOOL_DESCRIPTION,
            input_schema=ExecuteBashAction,
            output_schema=ExecuteBashObservation,
            annotations=execute_bash_tool.annotations,
            executor=executor,
        )
