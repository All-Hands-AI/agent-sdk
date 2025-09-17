"""Runtime tools package."""

from importlib import import_module
from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING


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
    "task_tracker_tool",
    "TaskTrackerAction",
    "TaskTrackerObservation",
    "TaskTrackerExecutor",
    "TaskTrackerTool",
    "BrowserToolSet",
]

try:
    __version__ = version("openhands-tools")
except PackageNotFoundError:
    __version__ = "0.0.0"  # fallback for editable/unbuilt environments


_mapping = {
    # execute_bash
    "execute_bash_tool": ("openhands.tools.execute_bash", "execute_bash_tool"),
    "ExecuteBashAction": ("openhands.tools.execute_bash", "ExecuteBashAction"),
    "ExecuteBashObservation": (
        "openhands.tools.execute_bash",
        "ExecuteBashObservation",
    ),
    "BashExecutor": ("openhands.tools.execute_bash", "BashExecutor"),
    "BashTool": ("openhands.tools.execute_bash", "BashTool"),
    # str_replace_editor
    "str_replace_editor_tool": (
        "openhands.tools.str_replace_editor",
        "str_replace_editor_tool",
    ),
    "StrReplaceEditorAction": (
        "openhands.tools.str_replace_editor",
        "StrReplaceEditorAction",
    ),
    "StrReplaceEditorObservation": (
        "openhands.tools.str_replace_editor",
        "StrReplaceEditorObservation",
    ),
    "FileEditorExecutor": ("openhands.tools.str_replace_editor", "FileEditorExecutor"),
    "FileEditorTool": ("openhands.tools.str_replace_editor", "FileEditorTool"),
    # task_tracker
    "task_tracker_tool": ("openhands.tools.task_tracker", "task_tracker_tool"),
    "TaskTrackerAction": ("openhands.tools.task_tracker", "TaskTrackerAction"),
    "TaskTrackerObservation": (
        "openhands.tools.task_tracker",
        "TaskTrackerObservation",
    ),
    "TaskTrackerExecutor": ("openhands.tools.task_tracker", "TaskTrackerExecutor"),
    "TaskTrackerTool": ("openhands.tools.task_tracker", "TaskTrackerTool"),
    # browser_use (heavy; only loads if you actually touch it)
    "BrowserToolSet": ("openhands.tools.browser_use", "BrowserToolSet"),
}


def __getattr__(name: str):
    if name in _mapping:
        mod_name, attr = _mapping[name]
        mod = import_module(mod_name)
        value = getattr(mod, attr)
        globals()[name] = value  # cache for next access
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# For type checkers / IDEs (no runtime import):
if TYPE_CHECKING:
    from openhands.tools.browser_use import BrowserToolSet
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
    from openhands.tools.task_tracker import (
        TaskTrackerAction,
        TaskTrackerExecutor,
        TaskTrackerObservation,
        TaskTrackerTool,
        task_tracker_tool,
    )
