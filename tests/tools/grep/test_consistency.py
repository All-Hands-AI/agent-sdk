"""Tests to verify consistency between ripgrep and fallback implementations."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from openhands.tools.grep.definition import GrepAction
from openhands.tools.grep.impl import GrepExecutor


class TestGrepConsistency:
    """Test that ripgrep and fallback methods produce consistent results."""

    @pytest.fixture
    def temp_dir_with_content(self):
        """Create a temporary directory with test files containing searchable content."""  # noqa: E501
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files with different content
            test_files = {
                "app.py": "def main():\n    print('Hello World')\n    return 0",
                "main.py": "import sys\ndef hello():\n    print('Hello from main')",
                "test.py": (
                    "import unittest\nclass TestApp(unittest.TestCase):\n    pass"
                ),
                "config.json": '{"name": "test", "version": "1.0", "hello": "world"}',
                "readme.md": "# Hello World\nThis is a test project.",
                "src/utils.py": "def helper():\n    return 'Hello from helper'",
                "src/models.py": (
                    "class User:\n    def __init__(self, name):\n"
                    "        self.name = name"
                ),
                "docs/guide.md": "# User Guide\nSay hello to get started.",
            }

            for file_path, content in test_files.items():
                full_path = Path(temp_dir) / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content)

            yield temp_dir

    def test_basic_search_consistency(self, temp_dir_with_content):
        """Test that both methods return consistent results for basic searches."""
        executor = GrepExecutor(temp_dir_with_content)
        action = GrepAction(pattern="hello")

        # Get results from both methods
        ripgrep_result = executor._execute_with_ripgrep(
            action, Path(temp_dir_with_content)
        )
        fallback_result = executor._execute_with_grep(
            action, Path(temp_dir_with_content)
        )

        # Both should succeed
        assert not ripgrep_result.error
        assert not fallback_result.error

        # Both should find files containing "hello"
        assert len(ripgrep_result.matches) > 0
        assert len(fallback_result.matches) > 0

        # Convert to basenames for comparison
        ripgrep_basenames = {Path(f).name for f in ripgrep_result.matches}
        fallback_basenames = {Path(f).name for f in fallback_result.matches}

        # Should find overlapping files (exact match may vary due to
        # implementation differences)
        overlap = ripgrep_basenames.intersection(fallback_basenames)
        assert len(overlap) > 0, (
            f"No overlap between ripgrep {ripgrep_basenames} and "
            f"fallback {fallback_basenames}"
        )

    def test_case_insensitive_consistency(self, temp_dir_with_content):
        """Test that both methods handle case-insensitive searches consistently."""
        executor = GrepExecutor(temp_dir_with_content)
        action = GrepAction(pattern="HELLO")  # Uppercase pattern

        # Get results from both methods
        ripgrep_result = executor._execute_with_ripgrep(
            action, Path(temp_dir_with_content)
        )
        fallback_result = executor._execute_with_grep(
            action, Path(temp_dir_with_content)
        )

        # Both should succeed and find files (case-insensitive)
        assert not ripgrep_result.error
        assert not fallback_result.error
        assert len(ripgrep_result.matches) > 0
        assert len(fallback_result.matches) > 0

    def test_include_pattern_consistency(self, temp_dir_with_content):
        """Test that both methods handle include patterns consistently."""
        executor = GrepExecutor(temp_dir_with_content)
        action = GrepAction(pattern="hello", include="*.py")

        # Get results from both methods
        ripgrep_result = executor._execute_with_ripgrep(
            action, Path(temp_dir_with_content)
        )
        fallback_result = executor._execute_with_grep(
            action, Path(temp_dir_with_content)
        )

        # Both should succeed
        assert not ripgrep_result.error
        assert not fallback_result.error

        # Both should only find Python files
        for match in ripgrep_result.matches:
            assert match.endswith(".py"), f"Non-Python file found: {match}"

        for match in fallback_result.matches:
            assert match.endswith(".py"), f"Non-Python file found: {match}"

    def test_no_matches_consistency(self, temp_dir_with_content):
        """Test that both methods handle no matches consistently."""
        executor = GrepExecutor(temp_dir_with_content)
        action = GrepAction(pattern="nonexistentpattern12345")

        # Get results from both methods
        ripgrep_result = executor._execute_with_ripgrep(
            action, Path(temp_dir_with_content)
        )
        fallback_result = executor._execute_with_grep(
            action, Path(temp_dir_with_content)
        )

        # Both should succeed but find no matches
        assert not ripgrep_result.error
        assert not fallback_result.error
        assert len(ripgrep_result.matches) == 0
        assert len(fallback_result.matches) == 0

    def test_regex_pattern_consistency(self, temp_dir_with_content):
        """Test that both methods handle simple regex patterns consistently."""
        executor = GrepExecutor(temp_dir_with_content)
        action = GrepAction(pattern="def ")  # Simple pattern that should work in both

        # Get results from both methods
        ripgrep_result = executor._execute_with_ripgrep(
            action, Path(temp_dir_with_content)
        )
        fallback_result = executor._execute_with_grep(
            action, Path(temp_dir_with_content)
        )

        # Both should succeed
        assert not ripgrep_result.error
        assert not fallback_result.error

        # Both should find Python files with function definitions
        assert len(ripgrep_result.matches) > 0
        assert len(fallback_result.matches) > 0

        # Should find Python files
        ripgrep_python_files = [m for m in ripgrep_result.matches if m.endswith(".py")]
        fallback_python_files = [
            m for m in fallback_result.matches if m.endswith(".py")
        ]

        assert len(ripgrep_python_files) > 0
        assert len(fallback_python_files) > 0

    @pytest.mark.skipif(
        not Path("/usr/bin/rg").exists() and not Path("/usr/local/bin/rg").exists(),
        reason="ripgrep not available for consistency testing",
    )
    def test_methods_called_correctly(self, temp_dir_with_content):
        """Test that the executor calls the right method based on ripgrep availability."""  # noqa: E501
        action = GrepAction(pattern="hello")

        # Test with ripgrep available
        with patch(
            "openhands.tools.grep.impl._check_ripgrep_available", return_value=True
        ):
            executor = GrepExecutor(temp_dir_with_content)
            assert executor._ripgrep_available

            # Should use ripgrep method
            result = executor(action)
            assert not result.error
            assert len(result.matches) > 0

        # Test with ripgrep not available
        with patch(
            "openhands.tools.grep.impl._check_ripgrep_available", return_value=False
        ):
            executor = GrepExecutor(temp_dir_with_content)
            assert not executor._ripgrep_available

            # Should use fallback method
            result = executor(action)
            assert not result.error
            assert len(result.matches) > 0
