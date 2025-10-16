"""Tests for the simplified TODO scanner functionality."""

import sys
import tempfile
from pathlib import Path


# Import the scanner functions
todo_mgmt_path = (
    Path(__file__).parent.parent.parent
    / "examples"
    / "github_workflows"
    / "03_todo_management"
)
sys.path.append(str(todo_mgmt_path))
from scanner import (  # noqa: E402  # type: ignore[import-not-found]
    scan_directory,
    scan_file_for_todos,
)


def test_scan_python_file_with_todos():
    """Test scanning a Python file with TODO comments."""
    content = """#!/usr/bin/env python3
def function1():
    # TODO(openhands): Add input validation
    return "hello"

def function2():
    # TODO(openhands): Implement error handling
    pass
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(content)
        f.flush()

        todos = scan_file_for_todos(Path(f.name))

    Path(f.name).unlink()

    assert len(todos) == 2
    assert todos[0]["description"] == "Add input validation"
    assert todos[1]["description"] == "Implement error handling"


def test_scan_typescript_file():
    """Test scanning a TypeScript file."""
    content = """function processData(): string {
    // TODO(openhands): Add validation
    return data;
}
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".ts", delete=False) as f:
        f.write(content)
        f.flush()

        todos = scan_file_for_todos(Path(f.name))

    Path(f.name).unlink()

    assert len(todos) == 1
    assert todos[0]["description"] == "Add validation"


def test_scan_java_file():
    """Test scanning a Java file."""
    content = """public class Test {
    public void method() {
        // TODO(openhands): Implement this method
        System.out.println("Hello");
    }
}
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".java", delete=False) as f:
        f.write(content)
        f.flush()

        todos = scan_file_for_todos(Path(f.name))

    Path(f.name).unlink()

    assert len(todos) == 1
    assert todos[0]["description"] == "Implement this method"


def test_scan_unsupported_file_extension():
    """Test that unsupported file extensions are ignored."""
    content = """// TODO(openhands): This should be ignored"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
        f.write(content)
        f.flush()

        todos = scan_file_for_todos(Path(f.name))

    Path(f.name).unlink()

    assert len(todos) == 0


def test_skip_processed_todos():
    """Test that TODOs with PR URLs are skipped."""
    content = """def test():
    # TODO(openhands): This should be found
    # TODO(in progress: https://github.com/owner/repo/pull/123)
    pass
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(content)
        f.flush()

        todos = scan_file_for_todos(Path(f.name))

    Path(f.name).unlink()

    assert len(todos) == 1
    assert todos[0]["description"] == "This should be found"


def test_scan_directory():
    """Test scanning a directory with multiple files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create Python file with TODO
        py_file = temp_path / "test.py"
        py_file.write_text("# TODO(openhands): Python todo\nprint('hello')")

        # Create TypeScript file with TODO
        ts_file = temp_path / "test.ts"
        ts_file.write_text("// TODO(openhands): TypeScript todo\nconsole.log('hello');")

        # Create unsupported file (should be ignored)
        js_file = temp_path / "test.js"
        js_file.write_text("// TODO(openhands): Should be ignored")

        todos = scan_directory(temp_path)

        assert len(todos) == 2
        descriptions = [todo["description"] for todo in todos]
        assert "Python todo" in descriptions
        assert "TypeScript todo" in descriptions


def test_empty_file():
    """Test scanning an empty file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("")
        f.flush()

        todos = scan_file_for_todos(Path(f.name))

    Path(f.name).unlink()

    assert len(todos) == 0
