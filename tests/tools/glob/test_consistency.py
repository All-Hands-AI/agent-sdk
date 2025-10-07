"""Tests to verify consistency between ripgrep and fallback implementations."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from openhands.tools.glob.definition import GlobAction
from openhands.tools.glob.impl import GlobExecutor


class TestGlobConsistency:
    """Test that ripgrep and fallback methods produce consistent results."""

    @pytest.fixture
    def temp_dir_with_files(self):
        """Create a temporary directory with test files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            test_files = {
                "app.py": "print('hello world')",
                "main.py": "def main(): pass",
                "test.py": "import unittest",
                "config.json": '{"name": "test"}',
                "readme.md": "# Test Project",
                "src/utils.py": "def helper(): pass",
                "src/models.py": "class User: pass",
                "docs/guide.md": "# Guide",
            }

            for file_path, content in test_files.items():
                full_path = Path(temp_dir) / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content)

            yield temp_dir

    def test_basic_pattern_consistency(self, temp_dir_with_files):
        """Test that both methods return consistent results for basic patterns."""
        executor = GlobExecutor(temp_dir_with_files)
        action = GlobAction(pattern="*.py")

        # Get results from both methods
        ripgrep_result = executor._execute_with_ripgrep(
            action, Path(temp_dir_with_files)
        )
        fallback_result = executor._execute_with_glob(action, Path(temp_dir_with_files))

        # Both should succeed
        assert not ripgrep_result.error
        assert not fallback_result.error

        # Both should find Python files
        assert len(ripgrep_result.files) > 0
        assert len(fallback_result.files) > 0

        # Convert to basenames for comparison (paths might differ slightly)
        ripgrep_basenames = {Path(f).name for f in ripgrep_result.files}
        fallback_basenames = {Path(f).name for f in fallback_result.files}

        # Should find the same files (at least the top-level Python files)
        expected_files = {"app.py", "main.py", "test.py"}
        assert expected_files.issubset(ripgrep_basenames)
        assert expected_files.issubset(fallback_basenames)

    def test_recursive_pattern_consistency(self, temp_dir_with_files):
        """Test that both methods handle recursive patterns consistently."""
        executor = GlobExecutor(temp_dir_with_files)
        action = GlobAction(pattern="**/*.py")

        # Get results from both methods
        ripgrep_result = executor._execute_with_ripgrep(
            action, Path(temp_dir_with_files)
        )
        fallback_result = executor._execute_with_glob(action, Path(temp_dir_with_files))

        # Both should succeed
        assert not ripgrep_result.error
        assert not fallback_result.error

        # Both should find Python files including in subdirectories
        assert len(ripgrep_result.files) >= 5  # At least 5 Python files
        assert len(fallback_result.files) >= 5

        # Convert to basenames for comparison
        ripgrep_basenames = {Path(f).name for f in ripgrep_result.files}
        fallback_basenames = {Path(f).name for f in fallback_result.files}

        # Should find files in subdirectories
        expected_files = {"app.py", "main.py", "test.py", "utils.py", "models.py"}
        assert expected_files.issubset(ripgrep_basenames)
        assert expected_files.issubset(fallback_basenames)

    def test_no_matches_consistency(self, temp_dir_with_files):
        """Test that both methods handle no matches consistently."""
        executor = GlobExecutor(temp_dir_with_files)
        action = GlobAction(pattern="*.nonexistent")

        # Get results from both methods
        ripgrep_result = executor._execute_with_ripgrep(
            action, Path(temp_dir_with_files)
        )
        fallback_result = executor._execute_with_glob(action, Path(temp_dir_with_files))

        # Both should succeed but find no files
        assert not ripgrep_result.error
        assert not fallback_result.error
        assert len(ripgrep_result.files) == 0
        assert len(fallback_result.files) == 0

    @pytest.mark.skipif(
        not Path("/usr/bin/rg").exists() and not Path("/usr/local/bin/rg").exists(),
        reason="ripgrep not available for consistency testing",
    )
    def test_methods_called_correctly(self, temp_dir_with_files):
        """Test that the executor calls the right method based on ripgrep availability."""  # noqa: E501
        action = GlobAction(pattern="*.py")

        # Test with ripgrep available
        with patch(
            "openhands.tools.glob.impl._check_ripgrep_available", return_value=True
        ):
            executor = GlobExecutor(temp_dir_with_files)
            assert executor._ripgrep_available

            # Should use ripgrep method
            result = executor(action)
            assert not result.error
            assert len(result.files) > 0

        # Test with ripgrep not available
        with patch(
            "openhands.tools.glob.impl._check_ripgrep_available",
            return_value=False,
        ):
            executor = GlobExecutor(temp_dir_with_files)
            assert not executor._ripgrep_available

            # Should use fallback method
            result = executor(action)
            assert not result.error
            assert len(result.files) > 0
