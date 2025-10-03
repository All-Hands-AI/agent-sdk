from openhands.tools.file_viewer.definition import FileViewerObservation
from openhands.tools.str_replace_editor.definition import StrReplaceEditorAction
from openhands.tools.str_replace_editor.impl import BaseFileExecutor


class FileViewerExecutor(BaseFileExecutor):
    """File viewer executor with read-only capabilities."""

    read_only: bool = True

    def __call__(self, action):  # type: ignore[override]
        """Execute a file viewer action by converting it to a file editor action."""
        # Convert FileViewerAction to StrReplaceEditorAction
        editor_action = StrReplaceEditorAction(
            command=action.command,
            path=action.path,
            view_range=action.view_range,
        )

        # Execute using the base file editor functionality
        result = super().__call__(editor_action)

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
