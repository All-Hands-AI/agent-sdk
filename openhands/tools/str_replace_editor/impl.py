from typing import TYPE_CHECKING

from openhands.sdk.tool import ToolExecutor
from openhands.tools.str_replace_editor.definition import (
    CommandLiteral,
    StrReplaceEditorAction,
    StrReplaceEditorObservation,
)
from openhands.tools.str_replace_editor.editor import FileEditor
from openhands.tools.str_replace_editor.exceptions import ToolError


if TYPE_CHECKING:
    pass


# Module-global editor instance (lazily initialized in file_editor)
_GLOBAL_EDITOR: FileEditor | None = None


class BaseFileExecutor(ToolExecutor):
    """Base executor class for file operations with configurable read-only mode."""

    def __init__(self, workspace_root: str | None = None, read_only: bool = False):
        self.editor = FileEditor(workspace_root=workspace_root)
        self.read_only = read_only

    def __call__(self, action: StrReplaceEditorAction) -> StrReplaceEditorObservation:
        # Enforce read-only restrictions
        if self.read_only and action.command not in ["view", "list"]:
            return StrReplaceEditorObservation(
                command=action.command,
                error=f"Operation '{action.command}' is not allowed in read-only mode. "
                "Only 'view' and 'list' commands are permitted.",
            )

        result: StrReplaceEditorObservation | None = None
        try:
            result = self.editor(
                command=action.command,
                path=action.path,
                file_text=action.file_text,
                view_range=action.view_range,
                old_str=action.old_str,
                new_str=action.new_str,
                insert_line=action.insert_line,
            )
        except ToolError as e:
            result = StrReplaceEditorObservation(
                command=action.command, error=e.message
            )
        assert result is not None, "file_editor should always return a result"
        return result


class FileEditorExecutor(BaseFileExecutor):
    """File editor executor with full read-write capabilities."""

    def __init__(self, workspace_root: str | None = None):
        super().__init__(workspace_root=workspace_root, read_only=False)


class FileViewerExecutor(ToolExecutor):
    """File viewer executor with read-only capabilities."""

    def __init__(self, workspace_root: str | None = None):
        self._base_executor = BaseFileExecutor(
            workspace_root=workspace_root, read_only=True
        )

    def __call__(self, action):
        """Execute a file viewer action by converting it to a file editor action."""
        # Import here to avoid circular imports
        from openhands.tools.file_viewer.definition import FileViewerObservation

        # Convert FileViewerAction to StrReplaceEditorAction
        editor_action = StrReplaceEditorAction(
            command=action.command,
            path=action.path,
            view_range=action.view_range,
        )

        # Execute using the base file editor functionality
        result = self._base_executor(editor_action)

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


def file_editor(
    command: CommandLiteral,
    path: str,
    file_text: str | None = None,
    view_range: list[int] | None = None,
    old_str: str | None = None,
    new_str: str | None = None,
    insert_line: int | None = None,
) -> StrReplaceEditorObservation:
    """A global FileEditor instance to be used by the tool."""

    global _GLOBAL_EDITOR
    if _GLOBAL_EDITOR is None:
        _GLOBAL_EDITOR = FileEditor()

    result: StrReplaceEditorObservation | None = None
    try:
        result = _GLOBAL_EDITOR(
            command=command,
            path=path,
            file_text=file_text,
            view_range=view_range,
            old_str=old_str,
            new_str=new_str,
            insert_line=insert_line,
        )
    except ToolError as e:
        result = StrReplaceEditorObservation(command=command, error=e.message)
    assert result is not None, "file_editor should always return a result"
    return result
