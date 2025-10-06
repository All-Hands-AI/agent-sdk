"""Planning file editor tool - combines read-only viewing with PLAN.md editing."""

from collections.abc import Sequence
from pathlib import Path
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


# Hardcoded plan filename
PLAN_FILENAME = "PLAN.md"


class PlanningFileEditorAction(Action):
    """Schema for planning file editor operations.

    Allows viewing any file but only editing PLAN.md.
    """

    command: Literal["view", "create", "str_replace", "insert"] = Field(
        description="The file operation to run:\n"
        "- 'view': Display file content or directory listing (works on any file)\n"
        "- 'create': Create a new file (only PLAN.md allowed)\n"
        "- 'str_replace': Replace text in a file (only PLAN.md allowed)\n"
        "- 'insert': Insert text at a line number (only PLAN.md allowed)"
    )
    path: str = Field(description="Absolute path to file or directory")
    file_text: str | None = Field(
        default=None,
        description="Required for 'create' command. The content of the file to be created.",  # noqa
    )
    old_str: str | None = Field(
        default=None,
        description="Required for 'str_replace'. The exact text to find and replace. "
        "Must match exactly (including whitespace).",
    )
    new_str: str | None = Field(
        default=None,
        description="Required for 'str_replace' and 'insert'. "
        "For 'str_replace': the new text to replace old_str. "
        "For 'insert': the text to insert after the specified line.",
    )
    insert_line: int | None = Field(
        default=None,
        ge=0,
        description="Required for 'insert'. The line number after which to insert new_str. "  # noqa
        "Use 0 to insert at the beginning of the file.",
    )
    view_range: list[int] | None = Field(
        default=None,
        description="Optional for 'view'. View only specific lines [start, end]. "
        "Example: [10, 20] shows lines 10-20. Use [start, -1] to show from start to end.",  # noqa
    )


class PlanningFileEditorObservation(Observation):
    """Observation from planning file editor operations."""

    command: Literal["view", "create", "str_replace", "insert"] = Field(
        description="The command that was executed."
    )
    output: str = Field(default="", description="Success message or file content.")
    error: str | None = Field(default=None, description="Error message if any.")

    @property
    def to_llm_content(self) -> Sequence[TextContent | ImageContent]:
        if self.error:
            return [TextContent(text=self.error)]
        return [TextContent(text=self.output)]


TOOL_DESCRIPTION = """File editor tool for planning agents with dual functionality:

1. **Read-only access to all files**: Use 'view' command to read any file or directory
   - If path is a text file, displays content with line numbers
   - If path is a directory, lists contents up to 2 levels deep
   - Supports view_range parameter to view specific line ranges

2. **Edit access to PLAN.md only**: Use 'create', 'str_replace', or 'insert' commands
   - PLAN.md is automatically initialized as an empty file at workspace root
   - All editing operations (create, str_replace, insert) are restricted to PLAN.md only

**Editing Rules (applies to PLAN.md only):**
1. EXACT MATCHING: The `old_str` must match exactly, including all whitespace
2. UNIQUENESS: The `old_str` must uniquely identify a single location in the file
   - Include sufficient context (3-5 lines recommended) to ensure uniqueness
3. REPLACEMENT: The `new_str` replaces `old_str` and must be different

Remember: When making multiple edits to PLAN.md, send all edits in a single message with multiple tool calls.
"""  # noqa


class PlanningFileEditorTool(
    ToolDefinition[PlanningFileEditorAction, PlanningFileEditorObservation]
):
    """A planning file editor tool with read-all, edit-PLAN.md-only access."""

    @classmethod
    def create(
        cls,
        conv_state: "ConversationState",
    ) -> Sequence["PlanningFileEditorTool"]:
        """Initialize PlanningFileEditorTool.

        Args:
            conv_state: Conversation state to get working directory from.
        """
        # Import here to avoid circular imports
        from openhands.tools.planning_file_editor.impl import (
            PlanningFileEditorExecutor,
        )

        working_dir = conv_state.workspace.working_dir
        workspace_root = Path(working_dir).resolve()
        plan_path = str(workspace_root / PLAN_FILENAME)

        # Initialize PLAN.md if it doesn't exist
        plan_file = Path(plan_path)
        if not plan_file.exists():
            plan_file.write_text("")

        # Create executor with restricted edit access to PLAN.md only
        executor = PlanningFileEditorExecutor(
            workspace_root=working_dir,
            plan_path=plan_path,
        )

        # Add working directory information to the tool description
        enhanced_description = (
            f"{TOOL_DESCRIPTION}\n\n"
            f"Your current working directory: {working_dir}\n"
            f"Your PLAN.md location: {plan_path}\n"
            f"This plan file will be accessible to other agents in the workflow."
        )

        return [
            cls(
                name="planning_file_editor",
                description=enhanced_description,
                action_type=PlanningFileEditorAction,
                observation_type=PlanningFileEditorObservation,
                annotations=ToolAnnotations(
                    title="planning_file_editor",
                    readOnlyHint=False,  # Can edit PLAN.md
                    destructiveHint=False,
                    idempotentHint=False,
                    openWorldHint=False,
                ),
                executor=executor,
            )
        ]
