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

    read_only: bool = False  # Class attribute - subclasses can override

    def __init__(self, workspace_root: str | None = None):
        self.editor = FileEditor(workspace_root=workspace_root)

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

    read_only: bool = False


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
