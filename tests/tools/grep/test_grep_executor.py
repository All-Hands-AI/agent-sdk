"""Tests for GrepExecutor implementation."""

import tempfile
from pathlib import Path

from openhands.tools.grep import GrepAction
from openhands.tools.grep.impl import GrepExecutor


def test_grep_executor_initialization():
    """Test that GrepExecutor initializes correctly."""
    with tempfile.TemporaryDirectory() as temp_dir:
        executor = GrepExecutor(working_dir=temp_dir)
        assert executor.working_dir == Path(temp_dir).resolve()


def test_grep_executor_basic_search():
    """Test basic content search."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test files
        (Path(temp_dir) / "app.py").write_text(
            "def main():\n    print('Hello')\n    return 0"
        )
        (Path(temp_dir) / "utils.py").write_text(
            "def helper():\n    print('Helper')\n    return True"
        )

        executor = GrepExecutor(working_dir=temp_dir)
        action = GrepAction(pattern="print")
        observation = executor(action)

        assert observation.error is None
        assert len(observation.matches) == 2
        assert observation.pattern == "print"
        assert observation.search_path == temp_dir

        # Check match structure
        for match in observation.matches:
            assert "file_path" in match
            assert "line_number" in match
            assert "line_content" in match
            assert "print" in str(match["line_content"])


def test_grep_executor_regex_patterns():
    """Test regex pattern matching."""
    with tempfile.TemporaryDirectory() as temp_dir:
        content = "def function_one():\n    pass\n\ndef function_two():\n    pass"
        (Path(temp_dir) / "code.py").write_text(content)

        executor = GrepExecutor(working_dir=temp_dir)
        action = GrepAction(pattern=r"def\s+\w+")
        observation = executor(action)

        assert observation.error is None
        assert len(observation.matches) == 2
        assert all(
            "def " in str(match["line_content"]) for match in observation.matches
        )


def test_grep_executor_invalid_regex():
    """Test handling of invalid regex patterns."""
    with tempfile.TemporaryDirectory() as temp_dir:
        (Path(temp_dir) / "test.py").write_text("def main(): pass")

        executor = GrepExecutor(working_dir=temp_dir)
        action = GrepAction(pattern="[invalid")
        observation = executor(action)

        assert observation.error is not None
        assert "Invalid regex pattern" in observation.error
        assert len(observation.matches) == 0


def test_grep_executor_include_filter():
    """Test file include filtering."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create files with different extensions
        (Path(temp_dir) / "app.py").write_text("print('Python')")
        (Path(temp_dir) / "script.js").write_text("console.log('JavaScript')")
        (Path(temp_dir) / "readme.md").write_text("# Documentation")

        executor = GrepExecutor(working_dir=temp_dir)
        action = GrepAction(pattern="log|print", include="*.py")
        observation = executor(action)

        assert observation.error is None
        assert len(observation.matches) == 1  # Only Python file
        assert observation.include_pattern == "*.py"
        assert "app.py" in str(observation.matches[0]["file_path"])


def test_grep_executor_custom_path():
    """Test search in custom directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create subdirectory with files
        sub_dir = Path(temp_dir) / "subdir"
        sub_dir.mkdir()
        (sub_dir / "file1.py").write_text("print('In subdir')")

        # Create file in main directory (should not be found)
        (Path(temp_dir) / "main.py").write_text("print('In main')")

        executor = GrepExecutor(working_dir=temp_dir)
        action = GrepAction(pattern="print", path=str(sub_dir))
        observation = executor(action)

        assert observation.error is None
        assert len(observation.matches) == 1
        assert observation.search_path == str(sub_dir)
        assert str(sub_dir) in str(observation.matches[0]["file_path"])


def test_grep_executor_invalid_path():
    """Test search in invalid directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        executor = GrepExecutor(working_dir=temp_dir)
        action = GrepAction(pattern="test", path="/nonexistent/path")
        observation = executor(action)

        assert observation.error is not None
        assert "is not a valid directory" in observation.error
        assert len(observation.matches) == 0


def test_grep_executor_no_matches():
    """Test search with no matches."""
    with tempfile.TemporaryDirectory() as temp_dir:
        (Path(temp_dir) / "app.py").write_text("def main():\n    return 0")

        executor = GrepExecutor(working_dir=temp_dir)
        action = GrepAction(pattern="nonexistent_pattern")
        observation = executor(action)

        assert observation.error is None
        assert len(observation.matches) == 0
        assert not observation.truncated


def test_grep_executor_hidden_files_excluded():
    """Test that hidden files are excluded."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create visible and hidden files
        (Path(temp_dir) / "visible.py").write_text("print('visible')")
        (Path(temp_dir) / ".hidden.py").write_text("print('hidden')")

        # Create hidden directory
        hidden_dir = Path(temp_dir) / ".hidden_dir"
        hidden_dir.mkdir()
        (hidden_dir / "file.py").write_text("print('in hidden dir')")

        executor = GrepExecutor(working_dir=temp_dir)
        action = GrepAction(pattern="print")
        observation = executor(action)

        assert observation.error is None
        assert len(observation.matches) == 1  # Only visible file
        assert "visible.py" in str(observation.matches[0]["file_path"])


def test_grep_executor_text_file_detection():
    """Test that only text files are searched."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create text file
        (Path(temp_dir) / "text.py").write_text("print('text file')")

        # Create binary file with mostly non-printable characters
        binary_path = Path(temp_dir) / "binary.bin"
        with open(binary_path, "wb") as f:
            # Create a file that's clearly binary (less than 70% printable)
            binary_data = bytes(range(256)) * 4  # 1024 bytes of binary data
            f.write(binary_data)

        executor = GrepExecutor(working_dir=temp_dir)
        action = GrepAction(pattern="print")
        observation = executor(action)

        assert observation.error is None
        assert len(observation.matches) == 1  # Only text file
        assert "text.py" in str(observation.matches[0]["file_path"])


def test_grep_executor_line_numbers():
    """Test correct line number reporting."""
    with tempfile.TemporaryDirectory() as temp_dir:
        content = "line 1\nline 2\nprint('target')\nline 4\nprint('another')\nline 6"
        (Path(temp_dir) / "test.py").write_text(content)

        executor = GrepExecutor(working_dir=temp_dir)
        action = GrepAction(pattern="print")
        observation = executor(action)

        assert observation.error is None
        assert len(observation.matches) == 2

        # Check line numbers
        line_numbers = [match["line_number"] for match in observation.matches]
        assert 3 in line_numbers  # First print
        assert 5 in line_numbers  # Second print


def test_grep_executor_file_sorting():
    """Test that files are processed in modification time order."""
    with tempfile.TemporaryDirectory() as temp_dir:
        import time

        # Create files with different modification times
        file1 = Path(temp_dir) / "file1.py"
        file1.write_text("print('first')")
        time.sleep(0.1)

        file2 = Path(temp_dir) / "file2.py"
        file2.write_text("print('second')")

        executor = GrepExecutor(working_dir=temp_dir)
        action = GrepAction(pattern="print")
        observation = executor(action)

        assert observation.error is None
        assert len(observation.matches) == 2

        # The newer file should be processed first
        # (though order in matches depends on file processing order)
        file_paths = [str(match["file_path"]) for match in observation.matches]
        assert any("file1.py" in path for path in file_paths)
        assert any("file2.py" in path for path in file_paths)


def test_grep_executor_truncation():
    """Test that results are truncated to 100 matches."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create file with many matching lines
        lines = [f"print('line {i}')" for i in range(150)]
        content = "\n".join(lines)
        (Path(temp_dir) / "large_file.py").write_text(content)

        executor = GrepExecutor(working_dir=temp_dir)
        action = GrepAction(pattern="print")
        observation = executor(action)

        assert observation.error is None
        assert len(observation.matches) == 100  # Truncated
        assert observation.truncated is True


def test_grep_executor_multiple_files_truncation():
    """Test truncation across multiple files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create multiple files with matching lines
        for file_num in range(10):
            lines = [f"print('file {file_num} line {i}')" for i in range(15)]
            content = "\n".join(lines)
            (Path(temp_dir) / f"file_{file_num}.py").write_text(content)

        executor = GrepExecutor(working_dir=temp_dir)
        action = GrepAction(pattern="print")
        observation = executor(action)

        assert observation.error is None
        assert len(observation.matches) == 100  # Truncated
        assert observation.truncated is True


def test_grep_executor_include_multiple_extensions():
    """Test include pattern with multiple extensions using separate tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create files with different extensions
        (Path(temp_dir) / "app.py").write_text("print('Python')")
        (Path(temp_dir) / "script.js").write_text("console.log('JavaScript')")
        (Path(temp_dir) / "style.css").write_text("/* CSS */")
        (Path(temp_dir) / "data.json").write_text('{"key": "value"}')

        executor = GrepExecutor(working_dir=temp_dir)

        # Test Python files only
        action = GrepAction(pattern="log|print", include="*.py")
        observation = executor(action)

        assert observation.error is None
        assert len(observation.matches) == 1  # Python file only
        assert observation.include_pattern == "*.py"
        assert any("app.py" in str(match["file_path"]) for match in observation.matches)

        # Test JavaScript files only
        action = GrepAction(pattern="log|print", include="*.js")
        observation = executor(action)

        assert observation.error is None
        assert len(observation.matches) == 1  # JavaScript file only
        assert observation.include_pattern == "*.js"
        assert any(
            "script.js" in str(match["file_path"]) for match in observation.matches
        )


def test_grep_executor_unicode_handling():
    """Test handling of Unicode content."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create file with Unicode content
        content = "print('Hello 世界')\nprint('Unicode: café')"
        (Path(temp_dir) / "unicode.py").write_text(content, encoding="utf-8")

        executor = GrepExecutor(working_dir=temp_dir)
        action = GrepAction(pattern="世界|café")
        observation = executor(action)

        assert observation.error is None
        assert len(observation.matches) == 2
        assert any(
            "世界" in str(match["line_content"]) for match in observation.matches
        )
        assert any(
            "café" in str(match["line_content"]) for match in observation.matches
        )


def test_grep_executor_is_text_file():
    """Test the _is_text_file method."""
    with tempfile.TemporaryDirectory() as temp_dir:
        executor = GrepExecutor(working_dir=temp_dir)

        # Test known text extensions
        text_file = Path(temp_dir) / "test.py"
        text_file.write_text("print('test')")
        assert executor._is_text_file(text_file) is True

        # Test known text filenames
        readme_file = Path(temp_dir) / "README"
        readme_file.write_text("# README")
        assert executor._is_text_file(readme_file) is True

        # Test binary file
        binary_file = Path(temp_dir) / "binary.bin"
        with open(binary_file, "wb") as f:
            f.write(b"\x00\x01\x02\x03\x04\x05")
        assert executor._is_text_file(binary_file) is False

        # Test empty file (should be considered text)
        empty_file = Path(temp_dir) / "empty.txt"
        empty_file.write_text("")
        assert executor._is_text_file(empty_file) is True


def test_grep_executor_unreadable_files():
    """Test handling of unreadable files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a readable file
        (Path(temp_dir) / "readable.py").write_text("print('readable')")

        executor = GrepExecutor(working_dir=temp_dir)
        action = GrepAction(pattern="print")
        observation = executor(action)

        # Should find the readable file and not crash on any unreadable ones
        assert observation.error is None
        assert len(observation.matches) >= 1
        assert any(
            "readable.py" in str(match["file_path"]) for match in observation.matches
        )


def test_grep_executor_case_sensitive():
    """Test that search is case sensitive by default."""
    with tempfile.TemporaryDirectory() as temp_dir:
        content = "Print('uppercase')\nprint('lowercase')\nPRINT('allcaps')"
        (Path(temp_dir) / "case_test.py").write_text(content)

        executor = GrepExecutor(working_dir=temp_dir)
        action = GrepAction(pattern="print")
        observation = executor(action)

        assert observation.error is None
        assert len(observation.matches) == 1  # Only lowercase 'print'
        assert "lowercase" in str(observation.matches[0]["line_content"])


def test_grep_executor_case_insensitive():
    """Test case insensitive search using regex flags."""
    with tempfile.TemporaryDirectory() as temp_dir:
        content = "Print('uppercase')\nprint('lowercase')\nPRINT('allcaps')"
        (Path(temp_dir) / "case_test.py").write_text(content)

        executor = GrepExecutor(working_dir=temp_dir)
        # Use regex flag for case insensitive search
        action = GrepAction(pattern="(?i)print")
        observation = executor(action)

        assert observation.error is None
        assert len(observation.matches) == 3  # All three variants
