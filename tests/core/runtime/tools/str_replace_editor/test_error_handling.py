"""Tests for error handling in file editor."""

from openhands.core.runtime.tools.str_replace_editor.impl import file_editor

from .conftest import assert_error_result


def test_validation_error_formatting():
    """Test that validation errors are properly formatted in the output."""
    result = file_editor(
        command="view",
        path="/nonexistent/file.txt",
    )
    assert_error_result(result)
    assert "does not exist" in result.error

    # Test directory validation for non-view commands
    result = file_editor(
        command="str_replace",
        path="/tmp",
        old_str="something",
        new_str="new",
    )
    assert_error_result(result)
    assert "directory and only the `view` command" in result.error


def test_str_replace_error_handling(temp_file):
    """Test error handling in str_replace command."""
    # Create a test file
    content = "line 1\nline 2\nline 3\n"
    with open(temp_file, "w") as f:
        f.write(content)

    # Test non-existent string
    result = file_editor(
        command="str_replace",
        path=temp_file,
        old_str="nonexistent",
        new_str="something",
    )
    assert_error_result(result)
    assert "did not appear verbatim" in result.error

    # Test multiple occurrences
    with open(temp_file, "w") as f:
        f.write("line\nline\nother")

    result = file_editor(
        command="str_replace",
        path=temp_file,
        old_str="line",
        new_str="new_line",
    )
    assert_error_result(result)
    assert "Multiple occurrences" in result.error
    assert "lines [1, 2]" in result.error


def test_view_range_validation(temp_file):
    """Test validation of view_range parameter."""
    # Create a test file
    content = "line 1\nline 2\nline 3\n"
    with open(temp_file, "w") as f:
        f.write(content)

    # Test invalid range format
    result = file_editor(
        command="view",
        path=temp_file,
        view_range=[1],  # Should be [start, end]
    )
    assert_error_result(result)
    assert "should be a list of two integers" in result.error

    # Test out of bounds range: should clamp to file end and show a warning
    result = file_editor(
        command="view",
        path=temp_file,
        view_range=[1, 10],  # File only has 3 lines
    )
    # This should succeed but show a warning
    assert result.error is None
    assert (
        "NOTE: We only show up to 3 since there're only 3 lines in this file."
        in result.output
    )

    # Test invalid range order
    result = file_editor(
        command="view",
        path=temp_file,
        view_range=[3, 1],  # End before start
    )
    assert_error_result(result)
    assert "should be greater than or equal to" in result.error


def test_insert_validation(temp_file):
    """Test validation in insert command."""
    # Create a test file
    content = "line 1\nline 2\nline 3\n"
    with open(temp_file, "w") as f:
        f.write(content)

    # Test insert at negative line
    result = file_editor(
        command="insert",
        path=temp_file,
        insert_line=-1,
        new_str="new line",
    )
    assert_error_result(result)
    assert "should be within the range" in result.error

    # Test insert beyond file length
    result = file_editor(
        command="insert",
        path=temp_file,
        insert_line=10,
        new_str="new line",
    )
    assert_error_result(result)
    assert "should be within the range" in result.error


def test_undo_validation(temp_file):
    """Test undo_edit validation."""
    # Create a test file
    content = "line 1\nline 2\nline 3\n"
    with open(temp_file, "w") as f:
        f.write(content)

    # Try to undo without any previous edits
    result = file_editor(
        command="undo_edit",
        path=temp_file,
    )
    assert_error_result(result)
    assert "No edit history found" in result.error
