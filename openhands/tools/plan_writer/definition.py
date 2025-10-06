"""Plan writer tool implementation."""

from collections.abc import Sequence
from typing import TYPE_CHECKING, Literal

from pydantic import Field


if TYPE_CHECKING:
    from openhands.sdk.conversation.state import ConversationState

from openhands.sdk.llm import ImageContent, TextContent
from openhands.sdk.tool import (
    Action,
    Observation,
    ToolAnnotations,
    ToolDefinition,
)


class PlanWriterAction(Action):
    """Schema for plan writing operations.

    All operations are restricted to PLAN.md only.
    Uses FileEditor commands editing.
    """

    command: Literal["view", "str_replace", "insert"] = Field(
        description="The editing command to run on PLAN.md:\n"
        "- 'view': Display the current content of PLAN.md\n"
        "- 'str_replace': Replace a specific section of text in PLAN.md\n"
        "- 'insert': Insert new text after a specific line number"
    )
    old_str: str | None = Field(
        default=None,
        description="Required for 'str_replace' command. The exact text to find and replace in PLAN.md. "  # noqa
        "Must match exactly (including whitespace).",
    )
    new_str: str | None = Field(
        default=None,
        description="Required for 'str_replace' and 'insert' commands. "
        "For 'str_replace': the new text to replace old_str with. "
        "For 'insert': the text to insert after the specified line.",
    )
    insert_line: int | None = Field(
        default=None,
        ge=0,
        description="Required for 'insert' command. The line number after which to insert new_str. "  # noqa
        "Use 0 to insert at the beginning of the file.",
    )
    view_range: list[int] | None = Field(
        default=None,
        description="Optional for 'view' command. View only specific lines [start, end]. "  # noqa
        "Example: [10, 20] shows lines 10-20. Use [start, -1] to show from start to end of file.",  # noqa
    )


class PlanWriterObservation(Observation):
    """Observation from plan writing operations."""

    command: Literal["view", "str_replace", "insert"] = Field(
        description="The command that was executed."
    )
    output: str = Field(default="", description="Success message or file content.")
    error: str | None = Field(default=None, description="Error message if any.")

    @property
    def to_llm_content(self) -> Sequence[TextContent | ImageContent]:
        if self.error:
            return [TextContent(text=self.error)]
        return [TextContent(text=self.output)]


TOOL_DESCRIPTION = """Plan writer tool for editing the PLAN.md file.

This tool is **restricted to only modify PLAN.md** in the workspace root.
PLAN.md is pre-initialized as an empty file when the planning agent starts.

1. EXACT MATCHING: The `old_str` parameter must match EXACTLY one or more consecutive lines from the file, including all whitespace and indentation. The tool will fail if `old_str` matches multiple locations or doesn't match exactly with the file content.

2. UNIQUENESS: The `old_str` must uniquely identify a single instance in the file:
   - Include sufficient context before and after the change point (3-5 lines recommended)
   - If not unique, the replacement will not be performed

3. REPLACEMENT: The `new_str` parameter should contain the edited lines that replace the `old_str`. Both strings must be different.

Remember: when making multiple file edits in a row to the same file, you should prefer to send all edits in a single message with multiple calls to this tool, rather than multiple messages with a single call each.
"""  # noqa # TODO make base prompt for editing rules


plan_writer_tool = ToolDefinition(
    name="plan_writer",
    action_type=PlanWriterAction,
    description=TOOL_DESCRIPTION,
    annotations=ToolAnnotations(
        title="plan_writer",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    ),
)


class PlanWriterTool(ToolDefinition[PlanWriterAction, PlanWriterObservation]):
    """A plan writer tool for planning agents."""

    @classmethod
    def create(
        cls,
        conv_state: "ConversationState",
    ) -> Sequence["PlanWriterTool"]:
        """Initialize PlanWriterTool with a PlanWriterExecutor.

        Args:
            conv_state: Conversation state to get working directory from.
        """
        # Import here to avoid circular imports
        from openhands.tools.plan_writer.impl import PlanWriterExecutor

        # Initialize the executor
        executor = PlanWriterExecutor(workspace_root=conv_state.workspace.working_dir)

        # Add working directory information to the tool description
        working_dir = conv_state.workspace.working_dir
        enhanced_description = (
            f"{TOOL_DESCRIPTION}\n\n"
            f"Your plan file location: {working_dir}/PLAN.md\n"
            f"This file will be accessible to other agents in the workflow."
        )

        # Initialize the parent Tool with the executor
        return [
            cls(
                name=plan_writer_tool.name,
                description=enhanced_description,
                action_type=PlanWriterAction,
                observation_type=PlanWriterObservation,
                annotations=plan_writer_tool.annotations,
                executor=executor,
            )
        ]
