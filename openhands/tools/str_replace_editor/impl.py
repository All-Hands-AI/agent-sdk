from openhands.sdk.tool import ToolExecutor
from openhands.tools.str_replace_editor.definition import (
    CommandLiteral,
    StrReplaceEditorAction,
    StrReplaceEditorObservation,
)
from openhands.tools.str_replace_editor.editor import FileEditor
from openhands.tools.str_replace_editor.exceptions import ToolError


# Module-global editor instance (lazily initialized in file_editor)
_GLOBAL_EDITOR: FileEditor | None = None


class FileEditorExecutor(ToolExecutor):
    def __init__(self):
        self.editor = FileEditor()

    def __call__(self, action: StrReplaceEditorAction) -> StrReplaceEditorObservation:
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
            result = StrReplaceEditorObservation(error=e.message)
        assert result is not None, "file_editor should always return a result"
        return result


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
        result = StrReplaceEditorObservation(error=e.message)
    assert result is not None, "file_editor should always return a result"
    return result
