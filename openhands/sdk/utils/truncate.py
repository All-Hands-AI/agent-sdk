"""Utility functions for truncating text content."""

# Default truncation limits
DEFAULT_BASH_TRUNCATE_LIMIT = 30_000
DEFAULT_TEXT_CONTENT_LIMIT = 50_000

# Default truncation notice
DEFAULT_TRUNCATE_NOTICE = (
    "<response clipped><NOTE>Due to the max output limit, only part of the full "
    "response has been shown to you.</NOTE>"
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
