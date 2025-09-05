"""Tests for truncate utility functions."""

from openhands.sdk.utils import (
    DEFAULT_TEXT_CONTENT_LIMIT,
    DEFAULT_TRUNCATE_NOTICE,
    maybe_truncate,
)


def test_maybe_truncate_no_limit():
    """Test that maybe_truncate returns original content when no limit is set."""
    content = "This is a test string"
    result = maybe_truncate(content, truncate_after=None)
    assert result == content


def test_maybe_truncate_under_limit():
    """Test that maybe_truncate returns original content when under limit."""
    content = "Short string"
    result = maybe_truncate(content, truncate_after=100)
    assert result == content


def test_maybe_truncate_over_limit():
    """Test that maybe_truncate truncates content when over limit using head-and-tail."""  # noqa: E501
    content = "A" * 1000
    limit = 200  # Use a larger limit to accommodate the notice
    result = maybe_truncate(content, truncate_after=limit)

    # Calculate expected head and tail
    notice_len = len(DEFAULT_TRUNCATE_NOTICE)
    available_chars = limit - notice_len
    half = available_chars // 2
    head_chars = half + (available_chars % 2)
    tail_chars = half
    expected = content[:head_chars] + DEFAULT_TRUNCATE_NOTICE + content[-tail_chars:]

    assert result == expected
    assert len(result) == limit


def test_maybe_truncate_custom_notice():
    """Test that maybe_truncate uses custom truncation notice with head-and-tail."""
    content = "A" * 100
    limit = 50
    custom_notice = " [TRUNCATED]"
    result = maybe_truncate(
        content, truncate_after=limit, truncate_notice=custom_notice
    )

    # Calculate expected head and tail with custom notice
    notice_len = len(custom_notice)
    available_chars = limit - notice_len
    half = available_chars // 2
    head_chars = half + (available_chars % 2)
    tail_chars = half
    expected = content[:head_chars] + custom_notice + content[-tail_chars:]

    assert result == expected
    assert len(result) == limit


def test_maybe_truncate_exact_limit():
    """Test that maybe_truncate doesn't truncate when exactly at limit."""
    content = "A" * 50
    limit = 50
    result = maybe_truncate(content, truncate_after=limit)
    assert result == content


def test_default_limits():
    """Test that default limits are reasonable values."""
    assert DEFAULT_TEXT_CONTENT_LIMIT == 50_000
    assert isinstance(DEFAULT_TRUNCATE_NOTICE, str)
    assert len(DEFAULT_TRUNCATE_NOTICE) > 0


def test_maybe_truncate_empty_string():
    """Test that maybe_truncate handles empty strings correctly."""
    result = maybe_truncate("", truncate_after=100)
    assert result == ""


def test_maybe_truncate_zero_limit():
    """Test that maybe_truncate handles zero limit correctly."""
    content = "test"
    result = maybe_truncate(content, truncate_after=0)
    # Zero limit is treated as no limit (same as None)
    assert result == content


def test_maybe_truncate_head_and_tail():
    """Test that maybe_truncate preserves head and tail content."""
    content = "BEGINNING" + "X" * 100 + "ENDING"
    limit = 50
    custom_notice = "[MIDDLE_TRUNCATED]"
    result = maybe_truncate(
        content, truncate_after=limit, truncate_notice=custom_notice
    )

    # Should preserve beginning and end
    assert result.startswith("BEGINNING")
    assert result.endswith("ENDING")
    assert custom_notice in result
    assert len(result) == limit


def test_maybe_truncate_notice_too_large():
    """Test behavior when truncation notice is larger than limit."""
    content = "A" * 100
    limit = 10
    large_notice = "X" * 20  # Larger than limit
    result = maybe_truncate(content, truncate_after=limit, truncate_notice=large_notice)

    # With simplified logic, it will still try to do head-and-tail
    # even if notice is larger than limit
    available_chars = limit - len(large_notice)  # This will be negative
    half = available_chars // 2  # This will be negative
    head_chars = half + (available_chars % 2)
    tail_chars = half
    expected = content[:head_chars] + large_notice + content[-tail_chars:]
    assert result == expected
