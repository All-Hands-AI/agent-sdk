"""FileViewerTool - A read-only tool for viewing files and directories."""

from collections.abc import Sequence
from typing import TYPE_CHECKING

from openhands.sdk.tool import ToolAnnotations, ToolDefinition
from openhands.tools.str_replace_editor.definition import (
    TOOL_VIEWING_DESCRIPTION,
    StrReplaceEditorAction,
    StrReplaceEditorObservation,
)


if TYPE_CHECKING:
    from openhands.sdk.conversation.state import ConversationState


class FileViewerTool(
    ToolDefinition[StrReplaceEditorAction, StrReplaceEditorObservation]
):
    """A read-only tool for viewing files and directories."""

    @classmethod
    def create(
        cls,
        conv_state: "ConversationState",
    ) -> Sequence["FileViewerTool"]:
        """Initialize FileViewerTool with a read-only FileEditorExecutor.

        Args:
            conv_state: Conversation state to get working directory from.
                         If provided, workspace_root will be taken from
                         conv_state.workspace
        """
        # Import here to avoid circular imports
        from openhands.tools.str_replace_editor.impl import FileEditorExecutor

        # Initialize the executor in read-only mode
        executor = FileEditorExecutor(
            workspace_root=conv_state.workspace.working_dir, read_only=True
        )

        # Add working directory information to the tool description
        # to guide the agent to use the correct directory instead of root
        working_dir = conv_state.workspace.working_dir
        enhanced_description = (
            f"{TOOL_VIEWING_DESCRIPTION}\n\n"
            f"Your current working directory is: {working_dir}\n"
            f"When exploring project structure, start with this directory "
            f"instead of the root filesystem."
        )

        # Create tool annotations for read-only tool
        annotations = ToolAnnotations(
            title="file_viewer",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        )

        # Initialize the parent Tool with the executor
        return [
            cls(
                name="file_viewer",
                description=enhanced_description,
                action_type=StrReplaceEditorAction,
                observation_type=StrReplaceEditorObservation,
                annotations=annotations,
                executor=executor,
            )
        ]
