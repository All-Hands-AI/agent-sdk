"""Common constants and utilities for tools."""

BASE_FILE_TOOL_DESCRIPTION = """Custom{editing_capabilities} tool for viewing{extra_viewing_capabilities} files and directories in plain-text format.
* State is persistent across command calls and discussions with the user
* If `path` is a text file, `view` displays the result of applying `cat -n`. If `path` is a directory, `view` lists non-hidden files and directories up to 2 levels deep{extra_features}
* If the tool generates a long output, it will be truncated and marked with `<response clipped>`
* When working with files, always use absolute files paths (starting with /){extra_features}
"""  # noqa
