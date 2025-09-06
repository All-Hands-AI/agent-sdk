"""Tests for basic file editor operations."""

from openhands.tools.str_replace_editor import file_editor

from .conftest import (
    assert_successful_result,
)


def test_file_editor_happy_path(temp_file):
    """Test basic str_replace operation."""
    old_str = "test file"
    new_str = "sample file"

    # Create test file
    with open(temp_file, "w") as f:
        f.write("This is a test file.\nThis file is for testing purposes.")

    # Call the `file_editor` function
    result = file_editor(
        command="str_replace",
        path=str(temp_file),
        old_str=old_str,
        new_str=new_str,
    )

    # Validate the result
    assert_successful_result(result, str(temp_file))
    assert (
        result.output is not None
        and "The file" in result.output
        and "has been edited" in result.output
    )
    assert result.output is not None and "This is a sample file." in result.output
    assert result.path == str(temp_file)
    assert result.prev_exist is True
    assert (
        result.old_content == "This is a test file.\nThis file is for testing purposes."
    )
    assert (
        result.new_content
        == "This is a sample file.\nThis file is for testing purposes."
    )

    # Ensure the file content was updated
    with open(temp_file, "r") as f:
        content = f.read()
    assert "This is a sample file." in content


def test_file_editor_view_operation(temp_file):
    """Test view operation with file containing special content."""
    # Create content that includes various patterns
    xml_content = """This is a file with XML tags parsing logic...
match = re.search(
    r'<oh_aci_output_[0-9a-f]{32}>(.*?)</oh_aci_output_[0-9a-f]{32}>',
    result,
    re.DOTALL,
)
...More text here.
"""

    with open(temp_file, "w") as f:
        f.write(xml_content)

    result = file_editor(
        command="view",
        path=str(temp_file),
    )

    # Validate the result
    assert_successful_result(result, str(temp_file))
    assert (
        result.output is not None
        and "Here's the result of running `cat -n`" in result.output
    )
    assert (
        result.output is not None
        and "This is a file with XML tags parsing logic..." in result.output
    )
    assert result.output is not None and "match = re.search(" in result.output
    assert result.output is not None and "...More text here." in result.output


def test_successful_operations(temp_file):
    """Test successful file operations and their output formatting."""
    # Create a test file
    content = "line 1\nline 2\nline 3\n"
    with open(temp_file, "w") as f:
        f.write(content)

    # Test view
    result = file_editor(
        command="view",
        path=str(temp_file),
    )
    assert_successful_result(result)
    assert (
        result.output is not None
        and "Here's the result of running `cat -n`" in result.output
    )
    assert result.output is not None and "line 1" in result.output

    # Test str_replace
    result = file_editor(
        command="str_replace",
        path=str(temp_file),
        old_str="line 2",
        new_str="replaced line",
    )
    assert_successful_result(result)
    assert result.output is not None and "has been edited" in result.output
    assert result.output is not None and "replaced line" in result.output

    # Test insert
    result = file_editor(
        command="insert",
        path=str(temp_file),
        insert_line=1,
        new_str="inserted line",
    )
    assert_successful_result(result)
    assert result.output is not None and "has been edited" in result.output
    assert result.output is not None and "inserted line" in result.output

    # Test undo
    result = file_editor(
        command="undo_edit",
        path=str(temp_file),
    )
    assert_successful_result(result)
    assert result.output is not None and "undone successfully" in result.output


def test_tab_expansion(temp_file):
    """Test that tabs are properly handled in file operations."""
    # Create a file with tabs
    content = "no tabs\n\tindented\nline\twith\ttabs\n"
    with open(temp_file, "w") as f:
        f.write(content)

    # Test view command
    result = file_editor(
        command="view",
        path=str(temp_file),
    )
    assert_successful_result(result)
    # Tabs should be preserved in output
    assert result.output is not None and "\tindented" in result.output
    assert result.output is not None and "line\twith\ttabs" in result.output

    # Test str_replace with tabs in old_str
    result = file_editor(
        command="str_replace",
        path=str(temp_file),
        old_str="line\twith\ttabs",
        new_str="replaced line",
    )
    assert_successful_result(result)
    assert result.output is not None and "replaced line" in result.output

    # Test str_replace with tabs in new_str
    result = file_editor(
        command="str_replace",
        path=str(temp_file),
        old_str="replaced line",
        new_str="new\tline\twith\ttabs",
    )
    assert_successful_result(result)
    assert result.output is not None and "new\tline\twith\ttabs" in result.output

    # Test insert with tabs
    result = file_editor(
        command="insert",
        path=str(temp_file),
        insert_line=1,
        new_str="\tindented\tline",
    )
    assert_successful_result(result)
    assert result.output is not None and "\tindented\tline" in result.output


def test_create_operation(temp_file):
    """Test file creation operation."""
    # Remove the temp file first
    temp_file.unlink()

    content = "This is a new file.\nWith multiple lines."

    result = file_editor(
        command="create",
        path=str(temp_file),
        file_text=content,
    )

    assert_successful_result(result, str(temp_file))
    assert result.output is not None and "created successfully" in result.output
    assert result.prev_exist is False
    assert result.new_content == content

    # Verify file was created with correct content
    with open(temp_file, "r") as f:
        file_content = f.read()
    assert file_content == content


def test_view_operation_truncation(temp_file):
    """Test that view operation truncates large files correctly."""
    from openhands.tools.str_replace_editor.utils.constants import (
        MAX_RESPONSE_LEN_CHAR,
        TEXT_FILE_CONTENT_TRUNCATED_NOTICE,
    )

    # Create a large file that exceeds the str_replace_editor's truncation limit
    large_content = "A" * (MAX_RESPONSE_LEN_CHAR + 1000)
    with open(temp_file, "w") as f:
        f.write(large_content)

    # Test view command
    result = file_editor(
        command="view",
        path=str(temp_file),
    )

    assert_successful_result(result)
    assert result.output is not None

    # Check that truncation notice is present
    assert TEXT_FILE_CONTENT_TRUNCATED_NOTICE in result.output

    # The content should be truncated before line numbers are added
    # So the final output will be longer than MAX_RESPONSE_LEN_CHAR due to formatting
    # but the original content was truncated
    assert "Here's the result of running `cat -n`" in result.output

    # With head-and-tail truncation, should contain both start and end content
    # The line numbers will show as "     1\tA..." at start and end with "A"
    assert "\tA" in result.output  # Should have A's with tab formatting
