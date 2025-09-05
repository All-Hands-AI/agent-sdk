"""Utility functions for truncating text content."""

# Default truncation limits
DEFAULT_BASH_TRUNCATE_LIMIT = 30_000
DEFAULT_TEXT_CONTENT_LIMIT = 50_000

# Legacy constants from str_replace_editor for backward compatibility
MAX_RESPONSE_LEN_CHAR: int = 16000

# Truncation notices
DEFAULT_TRUNCATE_NOTICE = (
    "<response clipped><NOTE>Due to the max output limit, only part of the full "
    "response has been shown to you.</NOTE>"
)

CONTENT_TRUNCATED_NOTICE = (
    "<response clipped><NOTE>Due to the max output limit, only part of the full "
    "response has been shown to you.</NOTE>"
)

TEXT_FILE_CONTENT_TRUNCATED_NOTICE: str = (
    "<response clipped><NOTE>Due to the max output limit, only part of this file "
    "has been shown to you. You should retry this tool after you have searched "
    "inside the file with `grep -n` in order to find the line numbers of what you "
    "are looking for.</NOTE>"
)

BINARY_FILE_CONTENT_TRUNCATED_NOTICE: str = (
    "<response clipped><NOTE>Due to the max output limit, only part of this file "
    "has been shown to you. Please use Python libraries to view the entire file "
    "or search for specific content within the file.</NOTE>"
)

DIRECTORY_CONTENT_TRUNCATED_NOTICE: str = (
    "<response clipped><NOTE>Due to the max output limit, only part of this "
    "directory has been shown to you. You should use `ls -la` instead to view "
    "large directories incrementally.</NOTE>"
)


def maybe_truncate(
    content: str,
    truncate_after: int | None = None,
    truncate_notice: str = DEFAULT_TRUNCATE_NOTICE,
) -> str:
    """
    Truncate content and append a notice if content exceeds the specified length.

    Args:
        content: The text content to potentially truncate
        truncate_after: Maximum length before truncation. If None, no truncation occurs
        truncate_notice: Notice to append when content is truncated

    Returns:
        Original content if under limit, or truncated content with notice
    """
    return (
        content
        if not truncate_after or len(content) <= truncate_after
        else content[:truncate_after] + truncate_notice
    )
