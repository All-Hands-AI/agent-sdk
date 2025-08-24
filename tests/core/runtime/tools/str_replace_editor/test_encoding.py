"""Unit tests for the encoding module."""

import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

"""Integration tests for editor operations with non-UTF-8 encoded files."""


import pytest

from openhands.core.runtime.tools.str_replace_editor import file_editor
from openhands.core.runtime.tools.str_replace_editor.utils.encoding import (
    EncodingManager,
)

from .conftest import parse_result

from cachetools import LRUCache


@pytest.fixture
def temp_file():
    """Create a temporary file for testing."""
    fd, path = tempfile.mkstemp()
    os.close(fd)
    yield Path(path)
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


@pytest.fixture
def encoding_manager():
    """Create an EncodingManager instance for testing."""
    return EncodingManager()


def test_init(encoding_manager):
    """Test initialization of EncodingManager."""
    assert isinstance(encoding_manager, EncodingManager)
    assert isinstance(encoding_manager._encoding_cache, LRUCache)
    assert encoding_manager.default_encoding == "utf-8"
    assert encoding_manager.confidence_threshold == 0.9


def test_detect_encoding_nonexistent_file(encoding_manager):
    """Test detecting encoding for a nonexistent file."""
    nonexistent_path = Path("/nonexistent/file.txt")
    encoding = encoding_manager.detect_encoding(nonexistent_path)
    assert encoding == encoding_manager.default_encoding


def test_detect_encoding_utf8(encoding_manager, temp_file):
    """Test detecting UTF-8 encoding."""
    # Create a UTF-8 encoded file
    with open(temp_file, "w", encoding="utf-8") as f:
        f.write("Hello, world! UTF-8 encoded text.")

    encoding = encoding_manager.detect_encoding(temp_file)
    assert encoding.lower() in ("utf-8", "ascii")


def test_detect_encoding_utf8_with_icon(encoding_manager, temp_file):
    """Test detecting UTF-8 encoding with a word and an emoji."""
    # Create a UTF-8 encoded file with a single word and an emoji
    with open(temp_file, "w", encoding="utf-8") as f:
        f.write("Hello 😊")

    encoding = encoding_manager.detect_encoding(temp_file)
    assert encoding.lower() == "utf-8"


def test_detect_encoding_cp1251(encoding_manager, temp_file):
    """Test detecting CP1251 encoding."""
    # Create a CP1251 encoded file with Cyrillic characters
    with open(temp_file, "wb") as f:
        f.write("Привет, мир! Текст в кодировке CP1251.".encode("cp1251"))

    encoding = encoding_manager.detect_encoding(temp_file)
    assert encoding.lower() in ("windows-1251", "cp1251")


def test_detect_encoding_low_confidence(encoding_manager, temp_file):
    """Test fallback to default encoding when confidence is low."""
    # Create a file with mixed encodings to confuse the detector
    with open(temp_file, "wb") as f:
        f.write(b"\x80\x81\x82\x83\x84\x85\x86\x87\x88\x89\x8a\x8b\x8c\x8d\x8e\x8f")

    # Mock chardet.detect to return low confidence
    with patch(
        "charset_normalizer.detect",
        return_value={"encoding": "ascii", "confidence": 0.3},
    ):
        encoding = encoding_manager.detect_encoding(temp_file)
        assert encoding == encoding_manager.default_encoding


def test_detect_encoding_none_result(encoding_manager, temp_file):
    """Test fallback to default encoding when chardet returns None for encoding."""
    with open(temp_file, "wb") as f:
        f.write(b"\x00\x01\x02\x03")  # Binary data

    # Mock chardet.detect to return None for encoding
    with patch(
        "charset_normalizer.detect", return_value={"encoding": None, "confidence": 0.0}
    ):
        encoding = encoding_manager.detect_encoding(temp_file)
        assert encoding == encoding_manager.default_encoding


def test_get_encoding_cache_hit(encoding_manager, temp_file):
    """Test that get_encoding uses cached values when available."""
    # Create a file
    with open(temp_file, "w", encoding="utf-8") as f:
        f.write("Hello, world!")

    # First call should detect encoding
    with patch.object(
        encoding_manager, "detect_encoding", return_value="utf-8"
    ) as mock_detect:
        encoding1 = encoding_manager.get_encoding(temp_file)
        assert encoding1 == "utf-8"
        mock_detect.assert_called_once()

    # Second call should use cache
    with patch.object(
        encoding_manager, "detect_encoding", return_value="utf-8"
    ) as mock_detect:
        encoding2 = encoding_manager.get_encoding(temp_file)
        assert encoding2 == "utf-8"
        mock_detect.assert_not_called()


def test_get_encoding_cache_invalidation(encoding_manager, temp_file):
    """Test that cache is invalidated when file is modified."""
    # Create a file
    with open(temp_file, "w", encoding="utf-8") as f:
        f.write("Hello, world!")

    # First call should detect encoding
    encoding1 = encoding_manager.get_encoding(temp_file)
    assert encoding1.lower() in ("utf-8", "ascii")

    # Wait a moment to ensure modification time will be different
    time.sleep(0.1)

    # Modify the file
    with open(temp_file, "w", encoding="utf-8") as f:
        f.write("Modified content")

    # Mock detect_encoding to verify it's called again
    with patch.object(
        encoding_manager, "detect_encoding", return_value="utf-8"
    ) as mock_detect:
        encoding2 = encoding_manager.get_encoding(temp_file)
        assert encoding2 == "utf-8"
        mock_detect.assert_called_once()


def test_with_encoding_decorator():
    """Test the with_encoding decorator."""

    # Create a mock class with a method that will be decorated
    class MockEditor:
        def __init__(self):
            self._encoding_manager = EncodingManager()

        @with_encoding
        def read_file(self, path, encoding="utf-8"):
            return f"Reading file with encoding: {encoding}"

    editor = MockEditor()

    # Test with a directory
    with patch.object(Path, "is_dir", return_value=True):
        with patch.object(
            editor._encoding_manager, "get_encoding"
        ) as mock_get_encoding:
            result = editor.read_file(Path("/some/dir"))
            assert result == "Reading file with encoding: utf-8"
            mock_get_encoding.assert_not_called()

    # Test with a nonexistent file
    with patch.object(Path, "is_dir", return_value=False):
        with patch.object(Path, "exists", return_value=False):
            result = editor.read_file(Path("/nonexistent/file.txt"))
            assert (
                result
                == f"Reading file with encoding: {editor._encoding_manager.default_encoding}"
            )

    # Test with an existing file
    with patch.object(Path, "is_dir", return_value=False):
        with patch.object(Path, "exists", return_value=True):
            with patch.object(
                editor._encoding_manager, "get_encoding", return_value="latin-1"
            ):
                result = editor.read_file(Path("/existing/file.txt"))
                assert result == "Reading file with encoding: latin-1"


def test_with_encoding_respects_provided_encoding():
    """Test that the with_encoding decorator respects explicitly provided encoding."""
    # The current implementation of with_encoding always calls get_encoding
    # but doesn't override the provided encoding if it exists in kwargs

    class MockEditor:
        def __init__(self):
            self._encoding_manager = EncodingManager()

        @with_encoding
        def read_file(self, path, encoding="utf-8"):
            return f"Reading file with encoding: {encoding}"

    editor = MockEditor()

    # Test with explicitly provided encoding
    with patch.object(Path, "is_dir", return_value=False):
        with patch.object(Path, "exists", return_value=True):
            with patch.object(
                editor._encoding_manager,
                "get_encoding",
                return_value="detected-encoding",
            ):
                result = editor.read_file(Path("/some/file.txt"), encoding="iso-8859-1")
                # The provided encoding should be used, not the detected one
                assert result == "Reading file with encoding: iso-8859-1"


def test_cache_size_limit(encoding_manager, temp_file):
    """Test that the cache size is limited and LRU entries are evicted."""
    # Create a small cache for testing
    encoding_manager = EncodingManager(max_cache_size=3)

    # Create a file
    with open(temp_file, "w", encoding="utf-8") as f:
        f.write("Test file")

    # Create 4 different paths (using the same file but with different paths)
    paths = [Path(f"{temp_file}.{i}") for i in range(4)]

    # Mock exists and getmtime to return consistent values
    with patch.object(Path, "exists", return_value=True):
        with patch.object(os.path, "getmtime", return_value=123456):
            with patch.object(
                encoding_manager, "detect_encoding", return_value="utf-8"
            ):
                # Access paths in order 0, 1, 2, 3
                for i, path in enumerate(paths):
                    encoding_manager.get_encoding(path)

                # After adding 4th item, the cache should still have 3 items
                assert len(encoding_manager._encoding_cache) == 3
                # Path 0 should have been evicted (LRU)
                assert str(paths[0]) not in encoding_manager._encoding_cache
                # Paths 1, 2, 3 should still be in the cache
                for j in range(1, 4):
                    assert str(paths[j]) in encoding_manager._encoding_cache


@pytest.fixture
def temp_non_utf8_file():
    """Create a temporary file with cp1251 encoding for testing."""
    fd, path = tempfile.mkstemp()
    os.close(fd)

    # Create a file with cp1251 encoding containing Russian text
    with open(path, "wb") as f:
        f.write("# -*- coding: cp1251 -*-\n\n".encode("cp1251"))
        f.write("# Тестовый файл с кириллицей\n".encode("cp1251"))
        f.write('text = "Привет, мир!"\n'.encode("cp1251"))
        f.write("numbers = [1, 2, 3, 4, 5]\n".encode("cp1251"))
        f.write('message = "Это тестовая строка"\n'.encode("cp1251"))

    yield Path(path)
    os.unlink(path)


def test_view_non_utf8_file(temp_non_utf8_file):
    """Test viewing a non-UTF-8 encoded file."""
    # View the file
    result = file_editor(
        command="view",
        path=str(temp_non_utf8_file),
    )

    # Parse the result
    result_json = parse_result(result)

    # Verify the content was read correctly
    assert "Привет, мир!" in result_json["formatted_output_and_error"]
    assert "Тестовый файл с кириллицей" in result_json["formatted_output_and_error"]
    assert "Это тестовая строка" in result_json["formatted_output_and_error"]


def test_view_range_non_utf8_file(temp_non_utf8_file):
    """Test viewing a specific range of a non-UTF-8 encoded file."""
    # View only lines 3-5
    result = file_editor(
        command="view",
        path=str(temp_non_utf8_file),
        view_range=[3, 5],
    )

    # Parse the result
    result_json = parse_result(result)

    # Verify the content was read correctly
    assert "Тестовый файл с кириллицей" in result_json["formatted_output_and_error"]
    assert "Привет, мир!" in result_json["formatted_output_and_error"]

    # Verify that line 6 is not included
    assert "Это тестовая строка" not in result_json["formatted_output_and_error"]


def test_str_replace_non_utf8_file(temp_non_utf8_file):
    """Test replacing text in a non-UTF-8 encoded file."""
    # Replace text
    result = file_editor(
        command="str_replace",
        path=str(temp_non_utf8_file),
        old_str="Привет, мир!",
        new_str="Здравствуй, мир!",
        enable_linting=False,
    )

    # Parse the result
    result_json = parse_result(result)

    # Verify the replacement was successful
    assert "Здравствуй, мир!" in result_json["formatted_output_and_error"]
    assert "Привет, мир!" not in result_json["formatted_output_and_error"]

    # Verify the file was saved with the correct encoding
    with open(temp_non_utf8_file, "rb") as f:
        content = f.read()

    try:
        decoded = content.decode("cp1251")
        assert "Здравствуй, мир!" in decoded
    except UnicodeDecodeError:
        pytest.fail("File was not saved with the correct encoding")


def test_insert_non_utf8_file(temp_non_utf8_file):
    """Test inserting text in a non-UTF-8 encoded file."""
    # Insert text after line 4
    result = file_editor(
        command="insert",
        path=str(temp_non_utf8_file),
        insert_line=4,
        new_str='new_var = "Новая переменная"',
        enable_linting=False,
    )

    # Parse the result
    result_json = parse_result(result)

    # Verify the insertion was successful
    assert "Новая переменная" in result_json["formatted_output_and_error"]

    # Verify the file was saved with the correct encoding
    with open(temp_non_utf8_file, "rb") as f:
        content = f.read()

    try:
        decoded = content.decode("cp1251")
        assert "Новая переменная" in decoded
    except UnicodeDecodeError:
        pytest.fail("File was not saved with the correct encoding")


def test_create_non_utf8_file():
    """Test creating a new file with non-UTF-8 content."""
    # Create a temporary path
    fd, path = tempfile.mkstemp()
    os.close(fd)
    os.unlink(path)  # Remove the file so we can create it with the editor

    try:
        # Create content with Russian characters
        content = "# -*- coding: cp1251 -*-\n\n"
        content += "# Новый файл с кириллицей\n"
        content += 'greeting = "Привет из нового файла!"\n'

        # Create the file
        result = file_editor(
            command="create",
            path=path,
            file_text=content,
            enable_linting=False,
        )

        # Parse the result
        result_json = parse_result(result)

        # Verify the file was created successfully
        assert "File created successfully" in result_json["formatted_output_and_error"]

        # Read the file with cp1251 encoding to verify content
        encoding_manager = EncodingManager()
        encoding = encoding_manager.detect_encoding(Path(path))

        with open(path, "r", encoding=encoding) as f:
            file_content = f.read()

        assert "Привет из нового файла!" in file_content
        assert "Новый файл с кириллицей" in file_content

    finally:
        # Clean up
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass


def test_undo_edit_non_utf8_file(temp_non_utf8_file):
    """Test undoing an edit in a non-UTF-8 encoded file."""
    # First, make a change
    file_editor(
        command="str_replace",
        path=str(temp_non_utf8_file),
        old_str="Привет, мир!",
        new_str="Здравствуй, мир!",
        enable_linting=False,
    )

    # Now undo the change
    result = file_editor(
        command="undo_edit",
        path=str(temp_non_utf8_file),
        enable_linting=False,
    )

    # Parse the result
    result_json = parse_result(result)

    # Verify the undo was successful
    assert "undone successfully" in result_json["formatted_output_and_error"]

    # Verify the original content was restored with the correct encoding
    with open(temp_non_utf8_file, "rb") as f:
        content = f.read()

    try:
        decoded = content.decode("cp1251")
        assert "Привет, мир!" in decoded
        assert "Здравствуй, мир!" not in decoded
    except UnicodeDecodeError:
        pytest.fail("File was not restored with the correct encoding")


def test_complex_workflow_non_utf8_file(temp_non_utf8_file):
    """Test a complex workflow with multiple operations on a non-UTF-8 encoded file."""
    # 1. View the file
    result = file_editor(
        command="view",
        path=str(temp_non_utf8_file),
    )
    result_json = parse_result(result)
    assert "Привет, мир!" in result_json["formatted_output_and_error"]

    # 2. Replace text
    result = file_editor(
        command="str_replace",
        path=str(temp_non_utf8_file),
        old_str="Привет, мир!",
        new_str="Здравствуй, мир!",
        enable_linting=False,
    )
    result_json = parse_result(result)
    assert "Здравствуй, мир!" in result_json["formatted_output_and_error"]

    # 3. Insert text
    result = file_editor(
        command="insert",
        path=str(temp_non_utf8_file),
        insert_line=5,
        new_str="# Добавленная строка\nboolean_var = True",
        enable_linting=False,
    )
    result_json = parse_result(result)
    assert "Добавленная строка" in result_json["formatted_output_and_error"]

    # 4. View specific range
    result = file_editor(
        command="view",
        path=str(temp_non_utf8_file),
        view_range=[5, 7],
    )
    result_json = parse_result(result)
    assert "Добавленная строка" in result_json["formatted_output_and_error"]
    assert "boolean_var = True" in result_json["formatted_output_and_error"]

    # 5. Undo the last edit
    result = file_editor(
        command="undo_edit",
        path=str(temp_non_utf8_file),
        enable_linting=False,
    )
    result_json = parse_result(result)
    assert "undone successfully" in result_json["formatted_output_and_error"]

    # 6. Verify the file content after all operations
    with open(temp_non_utf8_file, "rb") as f:
        content = f.read()

    try:
        decoded = content.decode("cp1251")
        assert "Здравствуй, мир!" in decoded  # From step 2
        assert "Добавленная строка" not in decoded  # Undone in step 5
    except UnicodeDecodeError:
        pytest.fail("File was not maintained with the correct encoding")


def test_mixed_encoding_workflow():
    """Test workflow with files of different encodings."""
    # Create two temporary files with different encodings
    fd1, path1 = tempfile.mkstemp()
    fd2, path2 = tempfile.mkstemp()
    os.close(fd1)
    os.close(fd2)

    try:
        # Create a cp1251 encoded file
        with open(path1, "wb") as f:
            f.write("# -*- coding: cp1251 -*-\n".encode("cp1251"))
            f.write('text_cp1251 = "Текст в кодировке CP1251"\n'.encode("cp1251"))

        # Create a UTF-8 encoded file
        with open(path2, "w", encoding="utf-8") as f:
            f.write("# -*- coding: utf-8 -*-\n")
            f.write('text_utf8 = "Текст в кодировке UTF-8"\n')

        # 1. View the cp1251 file
        result1 = file_editor(
            command="view",
            path=path1,
        )
        result_json1 = parse_result(result1)
        assert "Текст в кодировке CP1251" in result_json1["formatted_output_and_error"]

        # 2. View the UTF-8 file
        result2 = file_editor(
            command="view",
            path=path2,
        )
        result_json2 = parse_result(result2)
        assert "Текст в кодировке UTF-8" in result_json2["formatted_output_and_error"]

        # 3. Edit the cp1251 file
        result3 = file_editor(
            command="str_replace",
            path=path1,
            old_str="Текст в кодировке CP1251",
            new_str="Измененный текст в CP1251",
            enable_linting=False,
        )
        result_json3 = parse_result(result3)
        assert "Измененный текст в CP1251" in result_json3["formatted_output_and_error"]

        # 4. Edit the UTF-8 file
        result4 = file_editor(
            command="str_replace",
            path=path2,
            old_str="Текст в кодировке UTF-8",
            new_str="Измененный текст в UTF-8",
            enable_linting=False,
        )
        result_json4 = parse_result(result4)
        assert "Измененный текст в UTF-8" in result_json4["formatted_output_and_error"]

        # 5. Verify both files maintain their original encodings
        with open(path1, "rb") as f:
            content1 = f.read()
        with open(path2, "rb") as f:
            content2 = f.read()

        # CP1251 file should be decodable with CP1251
        try:
            decoded1 = content1.decode("cp1251")
            assert "Измененный текст в CP1251" in decoded1
        except UnicodeDecodeError:
            pytest.fail("CP1251 file was not saved with the correct encoding")

        # UTF-8 file should be decodable with UTF-8
        try:
            decoded2 = content2.decode("utf-8")
            assert "Измененный текст в UTF-8" in decoded2
        except UnicodeDecodeError:
            pytest.fail("UTF-8 file was not saved with the correct encoding")

    finally:
        # Clean up
        try:
            os.unlink(path1)
            os.unlink(path2)
        except FileNotFoundError:
            pass
