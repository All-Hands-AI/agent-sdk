"""Tests for openhands.tools package initialization and import handling."""

import pytest


def test_valid_import_from_tools():
    """Test that valid imports from openhands.tools work correctly."""
    from openhands.tools import BashTool, FileEditorTool

    # These should be importable without error
    assert BashTool is not None
    assert FileEditorTool is not None


def test_invalid_import_raises_attribute_error():
    """Test that importing a non-existent attribute raises AttributeError."""
    import openhands.tools

    with pytest.raises(
        AttributeError,
        match=r"module 'openhands\.tools' has no attribute 'NonExistentTool'",
    ):
        _ = openhands.tools.NonExistentTool


def test_lazy_import_caching():
    """Test that lazy imports are cached after first access."""
    import openhands.tools

    # First access should trigger import and caching
    bash_tool_1 = openhands.tools.BashTool

    # Second access should use cached value
    bash_tool_2 = openhands.tools.BashTool

    # Should be the same object (cached)
    assert bash_tool_1 is bash_tool_2
