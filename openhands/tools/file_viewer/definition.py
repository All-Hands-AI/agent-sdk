"""File viewer tool implementation - read-only version of file editor."""

from collections.abc import Sequence
from typing import TYPE_CHECKING

from pydantic import Field


if TYPE_CHECKING:
    from openhands.sdk.conversation.state import ConversationState

from openhands.sdk.llm import ImageContent, TextContent
from openhands.sdk.tool import Action, Observation, ToolAnnotations, ToolDefinition


class FileViewerAction(Action):
    """Schema for file viewer operations - read-only."""

    path: str = Field(description="Absolute path to file or directory.")
    view_range: list[int] | None = Field(
        default=None,
        description=(
            "Optional parameter. "
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

    @property
    def to_llm_content(self) -> Sequence[TextContent | ImageContent]:
        """Convert observation to LLM content."""
        return [TextContent(text=self.content)]


TOOL_DESCRIPTION = """Custom tool for viewing files and directories in plain-text format.
* If `path` is a text file, `view` displays the result of applying `cat -n`. If `path` is a directory, `view` lists non-hidden files and directories up to 2 levels deep
* If the tool generates a long output, it will be truncated and marked with `<response clipped>`
* When working with files, always use absolute files paths (starting with /)
"""  # noqa


class FileViewerTool(ToolDefinition[FileViewerAction, FileViewerObservation]):
    """A read-only file viewer tool that uses FileViewerExecutor."""

    @classmethod
    def create(
        cls,
        conv_state: "ConversationState",
        **kwargs,
    ) -> Sequence["FileViewerTool"]:
        """Create a FileViewerTool instance."""
        # Import here to avoid circular imports
        from openhands.tools.file_viewer.impl import FileViewerExecutor

        working_dir = conv_state.workspace.working_dir

        # Create a read-only executor
        executor = FileViewerExecutor(workspace_root=working_dir)

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
                executor=executor,
            )
        ]
