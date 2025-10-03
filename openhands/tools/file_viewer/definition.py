"""File viewer tool implementation - read-only version of file editor."""

from collections.abc import Sequence
from typing import TYPE_CHECKING, Literal

from pydantic import Field


if TYPE_CHECKING:
    from openhands.sdk.conversation.state import ConversationState
from rich.text import Text

from openhands.sdk.llm import ImageContent, TextContent
from openhands.sdk.tool import (
    Action,
    Observation,
    ToolAnnotations,
    ToolDefinition,
    ToolExecutor,
)


CommandLiteral = Literal["view"]


class FileViewerAction(Action):
    """Schema for file viewer operations - read-only."""

    command: CommandLiteral = Field(
        description="The commands to run. Only `view` is allowed for read-only access."
    )
    path: str = Field(description="Absolute path to file or directory.")
    view_range: list[int] | None = Field(
        default=None,
        description=(
            "Optional parameter of `view` command when `path` points to a file. "
            "If none is given, the full file is shown. If provided, the file will be "
            "shown in the indicated line number range, e.g. [11, 12] will show lines "
            "11 and 12. Indexing at 1 to start. Setting `[start_line, -1]` shows all "
            "lines from `start_line` to the end of the file."
        ),
    )


class FileViewerObservation(Observation):
    """Observation from file viewer operations."""

    content: str = Field(description="The content of the file or directory listing.")
    error: bool = Field(default=False, description="Whether an error occurred.")
    diff: str | None = Field(
        default=None, description="Diff visualization (not applicable for viewer)."
    )

    @property
    def to_llm_content(self) -> Sequence[TextContent | ImageContent]:
        """Convert observation to LLM content."""
        if self.diff:
            # This shouldn't happen for viewer, but handle gracefully
            diff_text = Text.from_ansi(self.diff)
            return [TextContent(text=diff_text.plain)]
        return [TextContent(text=self.content)]


TOOL_DESCRIPTION = """
Custom file viewer tool for viewing files and directories in plain-text format.
This is a read-only tool that only supports viewing operations.

* State is persistent across command calls and discussions with the user
* If `path` is a text file, `view` displays the result of applying `cat -n`. If `path` is a directory, `view` lists non-hidden files and directories up to 2 levels deep
* The following binary file extensions can be viewed in Markdown format: [".xlsx", ".pptx", ".wav", ".mp3", ".m4a", ".flac", ".pdf", ".docx"]. IT DOES NOT HANDLE IMAGES.
* If a `command` generates a long output, it will be truncated and marked with `<response clipped>`

Before using this tool:
1. Use the view tool to understand the file's contents and context
2. Verify the directory path is correct

When viewing files:
   - Always use absolute file paths (starting with /)

CRITICAL REQUIREMENTS FOR USING THIS TOOL:

1. READ-ONLY ACCESS: This tool only supports viewing files and directories. No editing operations are available.

2. VIEW OPERATION: Use the `view` command to inspect file contents or directory listings.
"""  # noqa


class FileViewerTool(ToolDefinition[FileViewerAction, FileViewerObservation]):
    """A read-only file viewer tool that uses FileEditorExecutor in read-only mode."""

    @classmethod
    def create(
        cls,
        conversation_state: "ConversationState",
        **kwargs,
    ) -> Sequence["FileViewerTool"]:
        """Create a FileViewerTool instance."""
        # Import here to avoid circular imports
        from openhands.tools.str_replace_editor.impl import FileEditorExecutor

        working_dir = conversation_state.workspace.working_dir

        # Create a read-only executor
        executor = FileEditorExecutor(workspace_root=working_dir, read_only=True)

        # Add working directory information to the tool description
        enhanced_description = (
            f"{TOOL_DESCRIPTION}\n\n"
            f"Your current working directory is: {working_dir}\n"
            f"When exploring project structure, start with this directory "
            f"instead of the root filesystem."
        )

        return [
            cls(
                name="file_viewer",
                action_type=FileViewerAction,
                observation_type=FileViewerObservation,
                description=enhanced_description,
                annotations=ToolAnnotations(
                    title="file_viewer",
                    readOnlyHint=True,
                    destructiveHint=False,
                    idempotentHint=True,
                    openWorldHint=False,
                ),
                executor=FileViewerExecutor(executor),
            )
        ]


class FileViewerExecutor(ToolExecutor[FileViewerAction, FileViewerObservation]):
    """Executor that adapts FileEditorExecutor for FileViewer actions."""

    def __init__(self, file_editor_executor):
        self.file_editor_executor = file_editor_executor

    def __call__(self, action: FileViewerAction) -> FileViewerObservation:
        """Execute a file viewer action by converting it to a file editor action."""
        # Import here to avoid circular imports
        from openhands.tools.str_replace_editor.definition import StrReplaceEditorAction

        # Convert FileViewerAction to StrReplaceEditorAction
        editor_action = StrReplaceEditorAction(
            command=action.command,
            path=action.path,
            view_range=action.view_range,
        )

        # Execute using the file editor executor
        result = self.file_editor_executor(editor_action)

        # Convert result to FileViewerObservation
        if result.error:
            return FileViewerObservation(
                content=result.error,
                error=True,
            )
        else:
            return FileViewerObservation(
                content=result.output,
                error=False,
            )
