"""BashTool subclass that inherits from Tool."""

from openhands.sdk.tool import Tool
from openhands.tools.execute_bash.definition import (
    TOOL_DESCRIPTION,
    ExecuteBashAction,
    ExecuteBashObservation,
    execute_bash_tool,
)
from openhands.tools.execute_bash.impl import BashExecutor


class BashTool(Tool[ExecuteBashAction, ExecuteBashObservation]):
    """A Tool subclass that automatically initializes a BashExecutor."""

    def __init__(
        self,
        working_dir: str,
        username: str | None = None,
    ):
        """Initialize BashTool with executor parameters.

        Args:
            working_dir: The working directory for bash commands
            username: Optional username for the bash session
        """
        # Initialize the executor
        executor = BashExecutor(working_dir=working_dir, username=username)

        # Initialize the parent Tool with the executor
        super().__init__(
            name=execute_bash_tool.name,
            description=TOOL_DESCRIPTION,
            input_schema=ExecuteBashAction,
            output_schema=ExecuteBashObservation,
            annotations=execute_bash_tool.annotations,
            executor=executor,
        )
