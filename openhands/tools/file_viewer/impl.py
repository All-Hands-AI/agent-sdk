from openhands.sdk.tool import ToolExecutor
from openhands.tools.file_viewer.definition import FileViewerObservation
from openhands.tools.str_replace_editor.definition import StrReplaceEditorAction
from openhands.tools.str_replace_editor.impl import FileEditorExecutor


class FileViewerExecutor(ToolExecutor):
    """File viewer executor that uses FileEditorExecutor in read-only mode."""

    def __init__(self, workspace_root: str | None = None):
        # Create a read-only FileEditorExecutor
        self.editor_executor = FileEditorExecutor(
            workspace_root=workspace_root, read_only=True
        )

    def __call__(self, action):
        """Execute a file viewer action by converting it to a file editor action."""
        # Convert FileViewerAction to StrReplaceEditorAction
        editor_action = StrReplaceEditorAction(
            command=action.command,
            path=action.path,
            view_range=action.view_range,
        )

        # Execute using the read-only file editor
        result = self.editor_executor(editor_action)

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
