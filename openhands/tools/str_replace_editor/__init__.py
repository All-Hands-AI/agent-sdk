from openhands.tools.str_replace_editor.definition import (
    FileEditorAction,
    FileEditorObservation,
    FileEditorTool,
    file_editor_tool,
)
from openhands.tools.str_replace_editor.impl import FileEditorExecutor, file_editor


# Backward compatibility aliases
StrReplaceEditorAction = FileEditorAction
StrReplaceEditorObservation = FileEditorObservation
str_replace_editor_tool = file_editor_tool

__all__ = [
    # New consistent names
    "file_editor_tool",
    "FileEditorAction",
    "FileEditorObservation",
    "file_editor",
    "FileEditorExecutor",
    "FileEditorTool",
    # Backward compatibility aliases
    "str_replace_editor_tool",
    "StrReplaceEditorAction",
    "StrReplaceEditorObservation",
]
