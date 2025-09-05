"""Utility functions for truncating text content in str_replace_editor."""

from openhands.sdk.utils.truncate import maybe_truncate
from openhands.tools.str_replace_editor.utils.prompts import (
    BINARY_FILE_CONTENT_TRUNCATED_NOTICE,
    CONTENT_TRUNCATED_NOTICE,
    DIRECTORY_CONTENT_TRUNCATED_NOTICE,
    TEXT_FILE_CONTENT_TRUNCATED_NOTICE,
)


# str_replace_editor specific constants
MAX_RESPONSE_LEN_CHAR: int = 16000


# Re-export the maybe_truncate function for backward compatibility
__all__ = [
    "maybe_truncate",
    "MAX_RESPONSE_LEN_CHAR",
    "CONTENT_TRUNCATED_NOTICE",
    "TEXT_FILE_CONTENT_TRUNCATED_NOTICE",
    "BINARY_FILE_CONTENT_TRUNCATED_NOTICE",
    "DIRECTORY_CONTENT_TRUNCATED_NOTICE",
]
