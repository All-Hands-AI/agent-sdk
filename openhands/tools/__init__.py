"""Runtime tools package."""

from openhands.tools.datadog_api import (
    DatadogTool,
    datadog_search_logs_tool,
)
from openhands.tools.execute_bash import (
    BashExecutor,
    BashTool,
    ExecuteBashAction,
    ExecuteBashObservation,
    execute_bash_tool,
)
from openhands.tools.github_api import (
    GitHubTool,
    github_clone_repo_tool,
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


__all__ = [
    "datadog_search_logs_tool",
    "DatadogTool",
    "execute_bash_tool",
    "ExecuteBashAction",
    "ExecuteBashObservation",
    "BashExecutor",
    "BashTool",
    "github_clone_repo_tool",
    "GitHubTool",
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
]

from importlib.metadata import PackageNotFoundError, version


try:
    __version__ = version("openhands-tools")
except PackageNotFoundError:
    __version__ = "0.0.0"  # fallback for editable/unbuilt environments
