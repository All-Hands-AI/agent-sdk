"""Runtime tools package."""

from openhands.tools.execute_bash import (
    BashExecutor,
    BashTool,
    ExecuteBashAction,
    ExecuteBashObservation,
    execute_bash_tool,
)
from openhands.tools.str_replace_editor import (
    FileEditorExecutor,
    FileEditorTool,
    StrReplaceEditorAction,
    StrReplaceEditorObservation,
    str_replace_editor_tool,
)
from openhands.tools.think import (
    ThinkAction,
    ThinkExecutor,
    ThinkObservation,
    ThinkTool,
    think_tool,
)


__all__ = [
    "execute_bash_tool",
    "ExecuteBashAction",
    "ExecuteBashObservation",
    "BashExecutor",
    "BashTool",
    "str_replace_editor_tool",
    "StrReplaceEditorAction",
    "StrReplaceEditorObservation",
    "FileEditorExecutor",
    "FileEditorTool",
    "think_tool",
    "ThinkAction",
    "ThinkObservation",
    "ThinkExecutor",
    "ThinkTool",
]

from importlib.metadata import PackageNotFoundError, version


try:
    __version__ = version("openhands-tools")
except PackageNotFoundError:
    __version__ = "0.0.0"  # fallback for editable/unbuilt environments
