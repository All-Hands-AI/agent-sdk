"""Unit tests for RemoteWorkspaceMixin class."""

from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import httpx

from openhands.sdk.workspace.models import CommandResult, FileOperationResult
from openhands.sdk.workspace.remote.remote_workspace_mixin import RemoteWorkspaceMixin


class TestRemoteWorkspaceMixin(RemoteWorkspaceMixin):
    """Test implementation of RemoteWorkspaceMixin for testing purposes."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


def test_remote_workspace_mixin_initialization():
    """Test RemoteWorkspaceMixin can be initialized with required parameters."""
    mixin = TestRemoteWorkspaceMixin(host="http://localhost:8000", api_key="test-key")

    assert mixin.host == "http://localhost:8000"
    assert mixin.api_key == "test-key"


def test_remote_workspace_mixin_initialization_without_api_key():
    """Test RemoteWorkspaceMixin can be initialized without API key."""
    mixin = TestRemoteWorkspaceMixin(host="http://localhost:8000")

    assert mixin.host == "http://localhost:8000"
    assert mixin.api_key is None


def test_host_normalization_in_post_init():
    """Test that host URL is normalized by removing trailing slash in
    model_post_init."""
    mixin = TestRemoteWorkspaceMixin(host="http://localhost:8000/")

    assert mixin.host == "http://localhost:8000"


def test_headers_property_with_api_key():
    """Test _headers property includes API key when present."""
    mixin = TestRemoteWorkspaceMixin(host="http://localhost:8000", api_key="test-key")

    headers = mixin._headers
    assert headers == {"X-Session-API-Key": "test-key"}


def test_headers_property_without_api_key():
    """Test _headers property is empty when no API key."""
    mixin = TestRemoteWorkspaceMixin(host="http://localhost:8000")

    headers = mixin._headers
    assert headers == {}


def test_execute_command_generator_basic_flow():
    """Test _execute_command_generator basic successful flow."""
    mixin = TestRemoteWorkspaceMixin(host="http://localhost:8000", api_key="test-key")

    # Mock responses
    start_response = Mock()
    start_response.raise_for_status = Mock()
    start_response.json.return_value = {"id": "cmd-123"}

    poll_response = Mock()
    poll_response.raise_for_status = Mock()
    poll_response.json.return_value = {
        "items": [
            {"kind": "BashOutput", "stdout": "hello\n", "stderr": "", "exit_code": 0}
        ]
    }

    generator = mixin._execute_command_generator("echo hello", "/tmp", 30.0)

    # First yield - start command
    start_kwargs = next(generator)
    assert start_kwargs["method"] == "POST"
    assert start_kwargs["url"] == "http://localhost:8000/api/bash/start_bash_command"
    assert start_kwargs["json"]["command"] == "echo hello"
    assert start_kwargs["json"]["cwd"] == "/tmp"
    assert start_kwargs["json"]["timeout"] == 30
    assert start_kwargs["headers"] == {"X-Session-API-Key": "test-key"}

    # Send start response
    poll_kwargs = generator.send(start_response)
    assert poll_kwargs["method"] == "GET"
    assert poll_kwargs["url"] == "http://localhost:8000/api/bash/bash_events/search"

    # Send poll response and get result
    try:
        generator.send(poll_response)
        assert False, "Generator should have stopped"
    except StopIteration as e:
        result = e.value
        assert isinstance(result, CommandResult)
        assert result.command == "echo hello"
        assert result.exit_code == 0
        assert result.stdout == "hello\n"
        assert result.stderr == ""
        assert result.timeout_occurred is False


def test_execute_command_generator_without_cwd():
    """Test _execute_command_generator works without cwd parameter."""
    mixin = TestRemoteWorkspaceMixin(host="http://localhost:8000")

    generator = mixin._execute_command_generator("echo hello", None, 30.0)

    # First yield - start command
    start_kwargs = next(generator)
    assert "cwd" not in start_kwargs["json"]


def test_execute_command_generator_with_path_cwd():
    """Test _execute_command_generator works with Path object for cwd."""
    mixin = TestRemoteWorkspaceMixin(host="http://localhost:8000")

    generator = mixin._execute_command_generator("echo hello", Path("/tmp/test"), 30.0)

    # First yield - start command
    start_kwargs = next(generator)
    assert start_kwargs["json"]["cwd"] == "/tmp/test"


@patch("time.sleep")
@patch("time.time")
def test_execute_command_generator_polling_loop(mock_time, mock_sleep):
    """Test _execute_command_generator polling loop behavior."""
    mixin = TestRemoteWorkspaceMixin(host="http://localhost:8000")

    # Mock time progression
    mock_time.side_effect = [0, 0.1, 0.2, 0.3]  # Simulate time passing

    # Mock responses
    start_response = Mock()
    start_response.raise_for_status = Mock()
    start_response.json.return_value = {"id": "cmd-123"}

    # First poll - no exit code yet
    poll_response_1 = Mock()
    poll_response_1.raise_for_status = Mock()
    poll_response_1.json.return_value = {
        "items": [
            {
                "kind": "BashOutput",
                "stdout": "processing...\n",
                "stderr": "",
                "exit_code": None,
            }
        ]
    }

    # Second poll - command completed
    poll_response_2 = Mock()
    poll_response_2.raise_for_status = Mock()
    poll_response_2.json.return_value = {
        "items": [
            {"kind": "BashOutput", "stdout": "done\n", "stderr": "", "exit_code": 0}
        ]
    }

    generator = mixin._execute_command_generator("long_command", None, 30.0)

    # Start command
    next(generator)

    # First poll
    generator.send(start_response)

    # Second poll
    generator.send(poll_response_1)

    # Final result
    try:
        generator.send(poll_response_2)
        assert False, "Generator should have stopped"
    except StopIteration as e:
        result = e.value
        assert result.stdout == "processing...\ndone\n"
        assert result.exit_code == 0

    # Verify sleep was called between polls
    mock_sleep.assert_called_with(0.1)


@patch("openhands.sdk.workspace.remote.remote_workspace_mixin.time")
def test_execute_command_generator_timeout(mock_time):
    """Test _execute_command_generator handles timeout correctly."""
    mixin = TestRemoteWorkspaceMixin(host="http://localhost:8000")

    # Mock time to simulate timeout
    mock_time.time.side_effect = [
        0,
        0,
        35,
    ]  # Start at 0, then jump to 35 (past 30s timeout)

    # Mock responses
    start_response = Mock()
    start_response.raise_for_status = Mock()
    start_response.json.return_value = {"id": "cmd-123"}

    poll_response = Mock()
    poll_response.raise_for_status = Mock()
    poll_response.json.return_value = {
        "items": [
            {
                "kind": "BashOutput",
                "stdout": "still running...\n",
                "stderr": "",
                "exit_code": None,  # No exit code - still running
            }
        ]
    }

    generator = mixin._execute_command_generator("slow_command", None, 30.0)

    # Start command
    next(generator)

    # Poll once
    generator.send(start_response)

    # Send poll response and get timeout result
    try:
        generator.send(poll_response)
        assert False, "Generator should have stopped"
    except StopIteration as e:
        result = e.value
        assert result.exit_code == -1
        assert result.timeout_occurred is True
        assert "timed out" in result.stderr


def test_execute_command_generator_exception_handling():
    """Test _execute_command_generator handles exceptions correctly."""
    mixin = TestRemoteWorkspaceMixin(host="http://localhost:8000")

    # Mock response that raises an exception
    start_response = Mock()
    start_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Server error", request=Mock(), response=Mock()
    )

    generator = mixin._execute_command_generator("failing_command", None, 30.0)

    # Start command
    next(generator)

    # Send failing response
    try:
        generator.send(start_response)
        assert False, "Generator should have stopped"
    except StopIteration as e:
        result = e.value
        assert result.exit_code == -1
        assert "Remote execution error" in result.stderr
        assert result.timeout_occurred is False


def test_file_upload_generator_basic_flow(temp_file):
    """Test _file_upload_generator basic successful flow."""
    mixin = TestRemoteWorkspaceMixin(host="http://localhost:8000", api_key="test-key")

    # Mock successful response
    upload_response = Mock()
    upload_response.raise_for_status = Mock()
    upload_response.json.return_value = {"success": True, "file_size": 12}

    generator = mixin._file_upload_generator(temp_file, "/remote/file.txt")

    # Get upload request
    upload_kwargs = next(generator)
    assert upload_kwargs["method"] == "POST"
    assert upload_kwargs["url"] == "http://localhost:8000/api/file/upload"
    assert upload_kwargs["data"]["destination_path"] == "/remote/file.txt"
    assert "file" in upload_kwargs["files"]
    assert upload_kwargs["headers"] == {"X-Session-API-Key": "test-key"}

    # Send response and get result
    try:
        generator.send(upload_response)
        assert False, "Generator should have stopped"
    except StopIteration as e:
        result = e.value
        assert isinstance(result, FileOperationResult)
        assert result.success is True
        assert result.source_path == str(temp_file)
        assert result.destination_path == "/remote/file.txt"
        assert result.file_size == 12


def test_file_upload_generator_with_path_objects(temp_file):
    """Test _file_upload_generator works with Path objects."""
    mixin = TestRemoteWorkspaceMixin(host="http://localhost:8000")

    upload_response = Mock()
    upload_response.raise_for_status = Mock()
    upload_response.json.return_value = {"success": True}

    generator = mixin._file_upload_generator(Path(temp_file), Path("/remote/file.txt"))

    upload_kwargs = next(generator)
    assert upload_kwargs["data"]["destination_path"] == "/remote/file.txt"


def test_file_upload_generator_file_not_found():
    """Test _file_upload_generator handles file not found error."""
    mixin = TestRemoteWorkspaceMixin(host="http://localhost:8000")

    generator = mixin._file_upload_generator(
        "/nonexistent/file.txt", "/remote/file.txt"
    )

    # Should handle FileNotFoundError
    try:
        next(generator)
        assert False, "Generator should have stopped"
    except StopIteration as e:
        result = e.value
        assert result.success is False
        assert (
            "No such file or directory" in result.error or "[Errno 2]" in result.error
        )


def test_file_upload_generator_http_error():
    """Test _file_upload_generator handles HTTP errors."""
    mixin = TestRemoteWorkspaceMixin(host="http://localhost:8000")

    with patch("builtins.open", mock_open(read_data="test content")):
        upload_response = Mock()
        upload_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Upload failed", request=Mock(), response=Mock()
        )

        generator = mixin._file_upload_generator("/local/file.txt", "/remote/file.txt")

        # Get upload request
        next(generator)

        # Send failing response
        try:
            generator.send(upload_response)
            assert False, "Generator should have stopped"
        except StopIteration as e:
            result = e.value
            assert result.success is False
            assert "Upload failed" in result.error


def test_file_download_generator_basic_flow(temp_dir):
    """Test _file_download_generator basic successful flow."""
    mixin = TestRemoteWorkspaceMixin(host="http://localhost:8000", api_key="test-key")

    # Mock successful response
    download_response = Mock()
    download_response.raise_for_status = Mock()
    download_response.content = b"downloaded content"

    destination = temp_dir / "downloaded_file.txt"
    generator = mixin._file_download_generator("/remote/file.txt", destination)

    # Get download request
    download_kwargs = next(generator)
    assert download_kwargs["method"] == "GET"
    assert download_kwargs["url"] == "/api/file/download"
    assert download_kwargs["params"]["file_path"] == "/remote/file.txt"
    assert download_kwargs["headers"] == {"X-Session-API-Key": "test-key"}

    # Send response and get result
    try:
        generator.send(download_response)
        assert False, "Generator should have stopped"
    except StopIteration as e:
        result = e.value
        assert isinstance(result, FileOperationResult)
        assert result.success is True
        assert result.source_path == "/remote/file.txt"
        assert result.destination_path == str(destination)
        assert result.file_size == len(b"downloaded content")

        # Verify file was written
        assert destination.exists()
        assert destination.read_bytes() == b"downloaded content"


def test_file_download_generator_with_path_objects(temp_dir):
    """Test _file_download_generator works with Path objects."""
    mixin = TestRemoteWorkspaceMixin(host="http://localhost:8000")

    download_response = Mock()
    download_response.raise_for_status = Mock()
    download_response.content = b"test content"

    destination = temp_dir / "test_file.txt"
    generator = mixin._file_download_generator(Path("/remote/file.txt"), destination)

    download_kwargs = next(generator)
    assert download_kwargs["params"]["file_path"] == "/remote/file.txt"


def test_file_download_generator_creates_directories(temp_dir):
    """Test _file_download_generator creates parent directories."""
    mixin = TestRemoteWorkspaceMixin(host="http://localhost:8000")

    download_response = Mock()
    download_response.raise_for_status = Mock()
    download_response.content = b"test content"

    # Nested path that doesn't exist
    destination = temp_dir / "nested" / "dirs" / "file.txt"
    generator = mixin._file_download_generator("/remote/file.txt", destination)

    next(generator)

    try:
        generator.send(download_response)
    except StopIteration as e:
        result = e.value
        assert result.success is True

        # Verify directories were created
        assert destination.parent.exists()
        assert destination.exists()


def test_file_download_generator_http_error():
    """Test _file_download_generator handles HTTP errors."""
    mixin = TestRemoteWorkspaceMixin(host="http://localhost:8000")

    download_response = Mock()
    download_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "File not found", request=Mock(), response=Mock()
    )

    generator = mixin._file_download_generator(
        "/remote/nonexistent.txt", "/local/file.txt"
    )

    # Get download request
    next(generator)

    # Send failing response
    try:
        generator.send(download_response)
        assert False, "Generator should have stopped"
    except StopIteration as e:
        result = e.value
        assert result.success is False
        assert "File not found" in result.error


def test_multiple_bash_output_events():
    """Test handling multiple BashOutput events in polling."""
    mixin = TestRemoteWorkspaceMixin(host="http://localhost:8000")

    # Mock responses
    start_response = Mock()
    start_response.raise_for_status = Mock()
    start_response.json.return_value = {"id": "cmd-123"}

    # Multiple events in single poll response
    poll_response = Mock()
    poll_response.raise_for_status = Mock()
    poll_response.json.return_value = {
        "items": [
            {
                "kind": "BashOutput",
                "stdout": "line 1\n",
                "stderr": "",
                "exit_code": None,
            },
            {
                "kind": "BashOutput",
                "stdout": "line 2\n",
                "stderr": "warning\n",
                "exit_code": None,
            },
            {"kind": "BashOutput", "stdout": "line 3\n", "stderr": "", "exit_code": 0},
        ]
    }

    generator = mixin._execute_command_generator("multi_output_command", None, 30.0)

    # Start command
    next(generator)

    # Poll and get result
    generator.send(start_response)

    try:
        generator.send(poll_response)
        assert False, "Generator should have stopped"
    except StopIteration as e:
        result = e.value
        assert result.stdout == "line 1\nline 2\nline 3\n"
        assert result.stderr == "warning\n"
        assert result.exit_code == 0


def test_non_bash_output_events_ignored():
    """Test that non-BashOutput events are ignored during polling."""
    mixin = TestRemoteWorkspaceMixin(host="http://localhost:8000")

    # Mock responses
    start_response = Mock()
    start_response.raise_for_status = Mock()
    start_response.json.return_value = {"id": "cmd-123"}

    # Mix of event types
    poll_response = Mock()
    poll_response.raise_for_status = Mock()
    poll_response.json.return_value = {
        "items": [
            {"kind": "SomeOtherEvent", "data": "should be ignored"},
            {
                "kind": "BashOutput",
                "stdout": "actual output\n",
                "stderr": "",
                "exit_code": 0,
            },
            {"kind": "AnotherEvent", "info": "also ignored"},
        ]
    }

    generator = mixin._execute_command_generator("test_command", None, 30.0)

    # Start command
    next(generator)

    # Poll and get result
    generator.send(start_response)

    try:
        generator.send(poll_response)
        assert False, "Generator should have stopped"
    except StopIteration as e:
        result = e.value
        assert result.stdout == "actual output\n"
        assert result.exit_code == 0
