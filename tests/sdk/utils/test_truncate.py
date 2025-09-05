"""Tests for truncate utility functions."""

from openhands.sdk.utils import (
    DEFAULT_BASH_TRUNCATE_LIMIT,
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
    """Test that maybe_truncate truncates content when over limit."""
    content = "A" * 100
    limit = 50
    result = maybe_truncate(content, truncate_after=limit)

    expected = "A" * limit + DEFAULT_TRUNCATE_NOTICE
    assert result == expected
    assert len(result) == limit + len(DEFAULT_TRUNCATE_NOTICE)


def test_maybe_truncate_custom_notice():
    """Test that maybe_truncate uses custom truncation notice."""
    content = "A" * 100
    limit = 50
    custom_notice = " [TRUNCATED]"
    result = maybe_truncate(
        content, truncate_after=limit, truncate_notice=custom_notice
    )

    expected = "A" * limit + custom_notice
    assert result == expected


def test_maybe_truncate_exact_limit():
    """Test that maybe_truncate doesn't truncate when exactly at limit."""
    content = "A" * 50
    limit = 50
    result = maybe_truncate(content, truncate_after=limit)
    assert result == content


def test_default_limits():
    """Test that default limits are reasonable values."""
    assert DEFAULT_BASH_TRUNCATE_LIMIT == 30_000
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
