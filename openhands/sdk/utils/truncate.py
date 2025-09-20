"""Utility functions for truncating text content."""

import tiktoken


def get_tokenizer(encoding_name: str = "o200k_base") -> tiktoken.Encoding:
    """Get a tiktoken tokenizer for the specified encoding.

    This function provides access to tiktoken encoders for token counting and
    text processing. By default, it uses the "o200k_base" encoding which is
    used by GPT-5 and other modern language models.

    Note: The token counts returned by this tokenizer are a best-effort
    approximation when used with non-OpenAI LLM providers. Different providers
    may use different tokenization schemes, so the actual token consumption
    may vary slightly from the counts provided by this function.

    Args:
        encoding_name: The name of the tiktoken encoding to use.
                      Defaults to "o200k_base" (GPT-5 encoding).
                      Other common encodings include:
                      - "cl100k_base" (GPT-4, GPT-3.5-turbo)
                      - "p50k_base" (GPT-3, Codex)

    Returns:
        A tiktoken.Encoding object for the specified encoding.

    Raises:
        ValueError: If the specified encoding is not available.
    """
    return tiktoken.get_encoding(encoding_name)


# Default truncation limits
DEFAULT_TEXT_CONTENT_LIMIT = 50_000
DEFAULT_TOKEN_LIMIT = 12_000  # Reasonable default for token-based truncation

# Default truncation notice
DEFAULT_TRUNCATE_NOTICE = (
    "<response clipped><NOTE>Due to the max output limit, only part of the full "
    "response has been shown to you.</NOTE>"
)


def maybe_truncate_by_tokens(
    content: str,
    max_tokens: int | None = None,
    truncate_notice: str = DEFAULT_TRUNCATE_NOTICE,
    encoding_name: str = "o200k_base",
) -> str:
    """
    Truncate the middle of content if it exceeds the specified token count.

    Keeps the head and tail of the content to preserve context at both ends.
    Uses tiktoken for accurate token counting.

    Args:
        content: The text content to potentially truncate
        max_tokens: Maximum tokens before truncation. If None, no truncation occurs
        truncate_notice: Notice to insert in the middle when content is truncated
        encoding_name: The tiktoken encoding to use (default: o200k_base for GPT-5)

    Returns:
        Original content if under limit, or truncated content with head and tail
        preserved
    """
    if not max_tokens or max_tokens < 0:
        return content

    try:
        encoding = get_tokenizer(encoding_name)
    except ValueError:
        # Fallback to character-based truncation if encoding is not available
        return maybe_truncate(
            content, max_tokens * 4, truncate_notice, use_tokens=False
        )

    tokens = encoding.encode(content)
    if len(tokens) <= max_tokens:
        return content

    # Calculate how many tokens we have for actual content
    notice_tokens = encoding.encode(truncate_notice)
    available_tokens = max_tokens - len(notice_tokens)

    if available_tokens <= 0:
        # If notice is too long, just return the notice
        return truncate_notice

    half = available_tokens // 2
    # Give extra token to head if odd number
    head_tokens = half + (available_tokens % 2)
    tail_tokens = half

    # Get head and tail content
    head_content = encoding.decode(tokens[:head_tokens])
    tail_content = encoding.decode(tokens[-tail_tokens:]) if tail_tokens > 0 else ""

    return head_content + truncate_notice + tail_content


def maybe_truncate(
    content: str,
    truncate_after: int | None = None,
    truncate_notice: str = DEFAULT_TRUNCATE_NOTICE,
    use_tokens: bool = False,
    encoding_name: str = "o200k_base",
) -> str:
    """
    Truncate the middle of content if it exceeds the specified length.

    Keeps the head and tail of the content to preserve context at both ends.

    Args:
        content: The text content to potentially truncate
        truncate_after: Maximum length before truncation. If None, no truncation occurs
        truncate_notice: Notice to insert in the middle when content is truncated
        use_tokens: If True, truncate by tokens instead of characters
        encoding_name: The tiktoken encoding to use when use_tokens=True

    Returns:
        Original content if under limit, or truncated content with head and tail
        preserved
    """
    if use_tokens:
        return maybe_truncate_by_tokens(
            content, truncate_after, truncate_notice, encoding_name
        )

    if not truncate_after or len(content) <= truncate_after or truncate_after < 0:
        return content

    # Calculate how much space we have for actual content
    available_chars = truncate_after - len(truncate_notice)
    half = available_chars // 2

    # Give extra character to head if odd number
    head_chars = half + (available_chars % 2)
    tail_chars = half

    # Keep head and tail, insert notice in the middle
    return content[:head_chars] + truncate_notice + content[-tail_chars:]
