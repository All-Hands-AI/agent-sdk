"""String replace editor tool implementation."""

import os
from collections.abc import Sequence
from typing import Literal

from pydantic import Field, PrivateAttr
from rich.text import Text

from openhands.sdk.llm import ImageContent, TextContent
from openhands.sdk.tool import ActionBase, ObservationBase, Tool, ToolAnnotations
from openhands.tools.str_replace_editor.utils.config import (
    DEFAULT_WORKSPACE_MOUNT_PATH_IN_SANDBOX,
)
from openhands.tools.str_replace_editor.utils.diff import visualize_diff


CommandLiteral = Literal["view", "create", "str_replace", "insert", "undo_edit"]


def _get_workspace_mount_path_from_env(runtime_type: str | None = None) -> str:
    """Get the workspace mount path from SANDBOX_VOLUMES environment variable.

    For LocalRuntime and CLIRuntime, returns the host path from SANDBOX_VOLUMES.
    For other runtimes, returns the default container path (/workspace).

    Args:
        runtime_type: The runtime type ('local', 'cli', 'docker', etc.)

    Returns:
        The workspace mount path in sandbox, defaults to '/workspace' if not found.
    """
    # For LocalRuntime/CLIRuntime, try to get host path from SANDBOX_VOLUMES
    if runtime_type in ("local", "cli"):
        sandbox_volumes = os.environ.get("SANDBOX_VOLUMES")
        if sandbox_volumes:
            # Split by commas to handle multiple mounts
            mounts = sandbox_volumes.split(",")

            # Check if any mount explicitly targets /workspace
            for mount in mounts:
                parts = mount.split(":")
                if len(parts) >= 2 and parts[1] == "/workspace":
                    host_path = os.path.abspath(parts[0])
                    return host_path

        # Fallback for local/CLI runtimes when SANDBOX_VOLUMES is not set:
        # Use current working directory as it's likely the workspace root
        return os.getcwd()

    # For all other runtimes (docker, remote, etc.), use default container path
    return DEFAULT_WORKSPACE_MOUNT_PATH_IN_SANDBOX


class StrReplaceEditorAction(ActionBase):
    """Schema for string replace editor operations."""

    command: CommandLiteral = Field(
        description="The commands to run. Allowed options are: `view`, `create`, "
        "`str_replace`, `insert`, `undo_edit`."
    )
    path: str = Field(
        description="Absolute path to file or directory, e.g. `/workspace/file.py` "
        "or `/workspace`."
    )
    file_text: str | None = Field(
        default=None,
        description="Required parameter of `create` command, with the content of "
        "the file to be created.",
    )
    old_str: str | None = Field(
        default=None,
        description="Required parameter of `str_replace` command containing the "
        "string in `path` to replace.",
    )
    new_str: str | None = Field(
        default=None,
        description="Optional parameter of `str_replace` command containing the "
        "new string (if not given, no string will be added). Required parameter "
        "of `insert` command containing the string to insert.",
    )
    insert_line: int | None = Field(
        default=None,
        description="Required parameter of `insert` command. The `new_str` will "
        "be inserted AFTER the line `insert_line` of `path`.",
    )
    view_range: list[int] | None = Field(
        default=None,
        description="Optional parameter of `view` command when `path` points to a "
        "file. If none is given, the full file is shown. If provided, the file "
        "will be shown in the indicated line number range, e.g. [11, 12] will "
        "show lines 11 and 12. Indexing at 1 to start. Setting `[start_line, "
        "-1]` shows all lines from `start_line` to the end of the file.",
    )


class StrReplaceEditorObservation(ObservationBase):
    """A ToolResult that can be rendered as a CLI output."""

    command: CommandLiteral = Field(
        description="The commands to run. Allowed options are: `view`, `create`, "
        "`str_replace`, `insert`, `undo_edit`."
    )
    output: str = Field(
        default="", description="The output message from the tool for the LLM to see."
    )
    path: str | None = Field(default=None, description="The file path that was edited.")
    prev_exist: bool = Field(
        default=True,
        description="Indicates if the file previously existed. If not, it was created.",
    )
    old_content: str | None = Field(
        default=None, description="The content of the file before the edit."
    )
    new_content: str | None = Field(
        default=None, description="The content of the file after the edit."
    )
    error: str | None = Field(default=None, description="Error message if any.")

    _diff_cache: Text | None = PrivateAttr(default=None)

    @property
    def agent_observation(self) -> Sequence[TextContent | ImageContent]:
        if self.error:
            return [TextContent(text=self.error)]
        return [TextContent(text=self.output)]

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation of this observation.

        Shows diff visualization for meaningful changes (file creation, successful
        edits), otherwise falls back to agent observation.
        """

        if not self._has_meaningful_diff:
            return super().visualize

        assert self.path is not None, "path should be set for meaningful diff"
        # Generate and cache diff visualization
        if not self._diff_cache:
            change_applied = self.command != "view" and not self.error
            self._diff_cache = visualize_diff(
                self.path,
                self.old_content,
                self.new_content,
                n_context_lines=2,
                change_applied=change_applied,
            )

        return self._diff_cache

    @property
    def _has_meaningful_diff(self) -> bool:
        """Check if there's a meaningful diff to display."""
        if self.error:
            return False

        if not self.path:
            return False

        if self.command not in ("create", "str_replace", "insert", "undo_edit"):
            return False

        # File creation case
        if self.command == "create" and self.new_content and not self.prev_exist:
            return True

        # File modification cases (str_replace, insert, undo_edit)
        if self.command in ("str_replace", "insert", "undo_edit"):
            # Need both old and new content to show meaningful diff
            if self.old_content is not None and self.new_content is not None:
                # Only show diff if content actually changed
                return self.old_content != self.new_content

        return False


Command = Literal[
    "view",
    "create",
    "str_replace",
    "insert",
    "undo_edit",
]


TOOL_DESCRIPTION = """Custom editing tool for viewing, creating and editing files in plain-text format
* State is persistent across command calls and discussions with the user
* If `path` is a text file, `view` displays the result of applying `cat -n`. If `path` is a directory, `view` lists non-hidden files and directories up to 2 levels deep
* The following binary file extensions can be viewed in Markdown format: [".xlsx", ".pptx", ".wav", ".mp3", ".m4a", ".flac", ".pdf", ".docx"]. IT DOES NOT HANDLE IMAGES.
* The `create` command cannot be used if the specified `path` already exists as a file
* If a `command` generates a long output, it will be truncated and marked with `<response clipped>`
* The `undo_edit` command will revert the last edit made to the file at `path`
* This tool can be used for creating and editing files in plain-text format.


Before using this tool:
1. Use the view tool to understand the file's contents and context
2. Verify the directory path is correct (only applicable when creating new files):
   - Use the view tool to verify the parent directory exists and is the correct location

When making edits:
   - Ensure the edit results in idiomatic, correct code
   - Do not leave the code in a broken state
   - Always use absolute file paths (starting with /)

CRITICAL REQUIREMENTS FOR USING THIS TOOL:

1. EXACT MATCHING: The `old_str` parameter must match EXACTLY one or more consecutive lines from the file, including all whitespace and indentation. The tool will fail if `old_str` matches multiple locations or doesn't match exactly with the file content.

2. UNIQUENESS: The `old_str` must uniquely identify a single instance in the file:
   - Include sufficient context before and after the change point (3-5 lines recommended)
   - If not unique, the replacement will not be performed

3. REPLACEMENT: The `new_str` parameter should contain the edited lines that replace the `old_str`. Both strings must be different.

Remember: when making multiple file edits in a row to the same file, you should prefer to send all edits in a single message with multiple calls to this tool, rather than multiple messages with a single call each.
"""  # noqa: E501


str_replace_editor_tool = Tool(
    name="str_replace_editor",
    action_type=StrReplaceEditorAction,
    description=TOOL_DESCRIPTION,
    annotations=ToolAnnotations(
        title="str_replace_editor",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False,
    ),
)


class FileEditorTool(Tool[StrReplaceEditorAction, StrReplaceEditorObservation]):
    """A Tool subclass that automatically initializes a FileEditorExecutor."""

    @classmethod
    def create(
        cls,
        workspace_root: str | None = None,
        workspace_mount_path_in_sandbox: str | None = None,
        runtime_type: str | None = None,
    ) -> "FileEditorTool":
        """Initialize FileEditorTool with a FileEditorExecutor.

        Args:
            workspace_root: Root directory for file operations
            workspace_mount_path_in_sandbox: Path to workspace in sandbox
            runtime_type: Runtime type for dynamic path detection
        """
        # Import here to avoid circular imports
        from openhands.tools.str_replace_editor.impl import FileEditorExecutor

        # If no workspace path is provided, try to get it from environment
        if workspace_mount_path_in_sandbox is None:
            workspace_mount_path_in_sandbox = _get_workspace_mount_path_from_env(
                runtime_type
            )

        # Create dynamic tool description with correct workspace path
        dynamic_description = TOOL_DESCRIPTION.replace(
            "/workspace", workspace_mount_path_in_sandbox
        )

        # Initialize the executor
        executor = FileEditorExecutor(workspace_root=workspace_root)

        # Create a dynamic action type with updated path description
        class DynamicStrReplaceEditorAction(StrReplaceEditorAction):
            path: str = Field(
                description=f"Absolute path to file or directory, e.g. "
                f"`{workspace_mount_path_in_sandbox}/file.py` "
                f"or `{workspace_mount_path_in_sandbox}`."
            )

        # Initialize the parent Tool with the executor
        return cls(
            name=str_replace_editor_tool.name,
            description=dynamic_description,
            action_type=DynamicStrReplaceEditorAction,
            observation_type=StrReplaceEditorObservation,
            annotations=str_replace_editor_tool.annotations,
            executor=executor,
        )
