"""FileEditorTool subclass that inherits from Tool."""

from openhands.sdk.tool import Tool
from openhands.tools.str_replace_editor.definition import (
    TOOL_DESCRIPTION,
    StrReplaceEditorAction,
    StrReplaceEditorObservation,
    str_replace_editor_tool,
)
from openhands.tools.str_replace_editor.impl import FileEditorExecutor


class FileEditorTool(Tool[StrReplaceEditorAction, StrReplaceEditorObservation]):
    """A Tool subclass that automatically initializes a FileEditorExecutor."""

    def __init__(self):
        """Initialize FileEditorTool with a FileEditorExecutor."""
        # Initialize the executor
        executor = FileEditorExecutor()

        # Initialize the parent Tool with the executor
        super().__init__(
            name=str_replace_editor_tool.name,
            description=TOOL_DESCRIPTION,
            input_schema=StrReplaceEditorAction,
            output_schema=StrReplaceEditorObservation,
            annotations=str_replace_editor_tool.annotations,
            executor=executor,
        )
