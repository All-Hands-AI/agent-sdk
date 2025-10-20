"""Utility functions for truncating text content."""

import hashlib
from pathlib import Path

from openhands.sdk.logger import get_logger


logger = get_logger(__name__)

# Default truncation limits
DEFAULT_TEXT_CONTENT_LIMIT = 50_000

# Default truncation notice
DEFAULT_TRUNCATE_NOTICE = (
    "<response clipped><NOTE>Due to the max output limit, only part of the full "
    "response has been shown to you.</NOTE>"
)

DEFAULT_TRUNCATE_NOTICE_WITH_PERSIST = (
    "<response clipped><NOTE>Due to the max output limit, only part of the full "
    "response has been shown to you. The complete output has been saved to "
    "{file_path} - you can use other tools to view the full content (truncated "
    "part starts around line {line_num}).</NOTE>"
)


def _save_full_content(content: str, save_dir: str, tool_prefix: str) -> str | None:
    """Save full content to the specified directory and return the file path."""

    save_dir_path = Path(save_dir)
    save_dir_path.mkdir(exist_ok=True)

    # Generate hash-based filename for deduplication
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:8]
    filename = f"{tool_prefix}_output_{content_hash}.txt"
    file_path = save_dir_path / filename

    # Only write if file doesn't exist (deduplication)
    if not file_path.exists():
        try:
            file_path.write_text(content, encoding="utf-8")
        except Exception as e:
            logger.debug(f"Failed to save full content to {file_path}: {e}")
            return None

    return str(file_path)


def maybe_truncate(
    content: str,
    truncate_after: int | None = None,
    truncate_notice: str = DEFAULT_TRUNCATE_NOTICE,
    save_dir: str | None = None,
    tool_prefix: str = "output",
) -> str:
    """
    Truncate the middle of content if it exceeds the specified length.

    Keeps the head and tail of the content to preserve context at both ends.
    Optionally saves the full content to a file for later investigation.

    Args:
        content: The text content to potentially truncate
        truncate_after: Maximum length before truncation. If None, no truncation occurs
        truncate_notice: Notice to insert in the middle when content is truncated
        save_dir: Working directory to save full content file in
        tool_prefix: Prefix for the saved file (e.g., "bash", "browser", "editor")

    Returns:
        Original content if under limit, or truncated content with head and tail
        preserved and reference to saved file if applicable
    """
    # Early returns for cases where no truncation is needed
    if not truncate_after or len(content) <= truncate_after or truncate_after < 0:
        return content

    # Edge case: truncate_after is too small to fit any content
    if len(truncate_notice) >= truncate_after:
        return truncate_notice[:truncate_after]

    # Calculate head size based on original notice (for consistent line number calc)
    available_chars = truncate_after - len(truncate_notice)
    half_chars = available_chars // 2
    head_chars = half_chars + (available_chars % 2)  # Give extra char to head if odd

    # Determine final notice by saving file first if requested
    final_notice = truncate_notice
    if save_dir:
        saved_file_path = _save_full_content(content, save_dir, tool_prefix)
        if saved_file_path:
            # Calculate line number where truncation happens (using head_chars)
            head_content_lines = len(content[:head_chars].splitlines())

            final_notice = DEFAULT_TRUNCATE_NOTICE_WITH_PERSIST.format(
                file_path=saved_file_path,
                line_num=head_content_lines + 1,  # +1 to indicate next line
            )

    # Calculate tail size based on final notice (head_chars stays consistent)
    final_available_chars = truncate_after - len(final_notice)
    tail_chars = max(0, final_available_chars - head_chars)

    # Assemble final result
    return content[:head_chars] + final_notice + content[-tail_chars:]
