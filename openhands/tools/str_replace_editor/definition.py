"""String replace editor tool implementation."""

from difflib import SequenceMatcher
from typing import Literal

from pydantic import Field

from openhands.sdk.llm import ImageContent, TextContent
from openhands.sdk.tool import ActionBase, ObservationBase, Tool, ToolAnnotations


CommandLiteral = Literal["view", "create", "str_replace", "insert", "undo_edit"]


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

    def __init__(self, **data):
        super().__init__(**data)
        self._diff_cache: str | None = None

    @property
    def agent_observation(self) -> list[TextContent | ImageContent]:
        if self.error:
            return [TextContent(text=self.error)]
        return [TextContent(text=self.output)]

    def get_edit_groups(self, n_context_lines: int = 2) -> list[dict[str, list[str]]]:
        """Get the edit groups showing changes between old and new content.

        Args:
            n_context_lines: Number of context lines to show around each change.

        Returns:
            A list of edit groups, where each group contains before/after edits.
        """
        if self.old_content is None or self.new_content is None:
            return []
        old_lines = self.old_content.split("\n")
        new_lines = self.new_content.split("\n")
        # Borrowed from difflib.unified_diff to directly parse into structured format
        edit_groups: list[dict] = []
        for group in SequenceMatcher(None, old_lines, new_lines).get_grouped_opcodes(
            n_context_lines
        ):
            # Take the max line number in the group
            _indent_pad_size = len(str(group[-1][3])) + 1  # +1 for "*" prefix
            cur_group: dict[str, list[str]] = {
                "before_edits": [],
                "after_edits": [],
            }
            for tag, i1, i2, j1, j2 in group:
                if tag == "equal":
                    for idx, line in enumerate(old_lines[i1:i2]):
                        line_num = i1 + idx + 1
                        cur_group["before_edits"].append(
                            f"{line_num:>{_indent_pad_size}}|{line}"
                        )
                    for idx, line in enumerate(new_lines[j1:j2]):
                        line_num = j1 + idx + 1
                        cur_group["after_edits"].append(
                            f"{line_num:>{_indent_pad_size}}|{line}"
                        )
                    continue
                if tag in {"replace", "delete"}:
                    for idx, line in enumerate(old_lines[i1:i2]):
                        line_num = i1 + idx + 1
                        cur_group["before_edits"].append(
                            f"-{line_num:>{_indent_pad_size - 1}}|{line}"
                        )
                if tag in {"replace", "insert"}:
                    for idx, line in enumerate(new_lines[j1:j2]):
                        line_num = j1 + idx + 1
                        cur_group["after_edits"].append(
                            f"+{line_num:>{_indent_pad_size - 1}}|{line}"
                        )
            edit_groups.append(cur_group)
        return edit_groups

    def visualize_diff(
        self,
        n_context_lines: int = 2,
        change_applied: bool = True,
    ) -> str:
        """Visualize the diff of the string replacement edit.

        Instead of showing the diff line by line, this function shows each hunk
        of changes as a separate entity.

        Args:
            n_context_lines: Number of context lines to show before/after changes.
            change_applied: Whether changes are applied. If false, shows as
                attempted edit.

        Returns:
            A string containing the formatted diff visualization.
        """
        # Use cached diff if available
        if self._diff_cache is not None:
            return self._diff_cache

        # Check if there are any changes
        if change_applied and self.old_content == self.new_content:
            msg = "(no changes detected. Please make sure your edits change "
            msg += "the content of the existing file.)\n"
            self._diff_cache = msg
            return self._diff_cache

        edit_groups = self.get_edit_groups(n_context_lines=n_context_lines)

        if change_applied:
            header = f"[File {self.path} edited with "
            header += f"{len(edit_groups)} changes.]"
        else:
            header = f"[Changes are NOT applied to {self.path} - Here's how "
            header += "the file looks like if changes are applied.]"
        result = [header]

        op_type = "edit" if change_applied else "ATTEMPTED edit"
        for i, cur_edit_group in enumerate(edit_groups):
            if i != 0:
                result.append("-------------------------")
            result.append(f"[begin of {op_type} {i + 1} / {len(edit_groups)}]")
            result.append(f"(content before {op_type})")
            result.extend(cur_edit_group["before_edits"])
            result.append(f"(content after {op_type})")
            result.extend(cur_edit_group["after_edits"])
            result.append(f"[end of {op_type} {i + 1} / {len(edit_groups)}]")

        # Cache the result
        self._diff_cache = "\n".join(result)
        return self._diff_cache


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

    def __init__(self):
        """Initialize FileEditorTool with a FileEditorExecutor."""
        # Import here to avoid circular imports
        from openhands.tools.str_replace_editor.impl import FileEditorExecutor

        # Initialize the executor
        executor = FileEditorExecutor()

        # Initialize the parent Tool with the executor
        super().__init__(
            name=str_replace_editor_tool.name,
            description=TOOL_DESCRIPTION,
            action_type=StrReplaceEditorAction,
            observation_type=StrReplaceEditorObservation,
            annotations=str_replace_editor_tool.annotations,
            executor=executor,
        )
