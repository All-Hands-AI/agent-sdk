from openhands.sdk.tool import ToolExecutor
from openhands.tools.file_editor.definition import FileEditorAction
from openhands.tools.file_editor.impl import FileEditorExecutor
from openhands.tools.file_viewer.definition import FileViewerObservation


class FileViewerExecutor(ToolExecutor):
    """File viewer executor that uses FileEditorExecutor in read-only mode."""

    def __init__(self, workspace_root: str | None = None):
        # Create a read-only FileEditorExecutor
        self.editor_executor = FileEditorExecutor(
            workspace_root=workspace_root, read_only=True
        )

    def __call__(self, action):
        """Execute a file viewer action by converting it to a file editor action."""
        # Convert FileViewerAction to FileEditorAction
        editor_action = FileEditorAction(
            command="view",
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
