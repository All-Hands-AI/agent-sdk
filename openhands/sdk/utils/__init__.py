"""Utility functions for the OpenHands SDK."""

from .protocol import ListLike
from .truncate import (
    DEFAULT_TEXT_CONTENT_LIMIT,
    DEFAULT_TOKEN_LIMIT,
    DEFAULT_TRUNCATE_NOTICE,
    get_tokenizer,
    maybe_truncate,
    maybe_truncate_by_tokens,
)


__all__ = [
    "DEFAULT_TEXT_CONTENT_LIMIT",
    "DEFAULT_TOKEN_LIMIT",
    "DEFAULT_TRUNCATE_NOTICE",
    "get_tokenizer",
    "maybe_truncate",
    "maybe_truncate_by_tokens",
    "ListLike",
]
